<?php
// Shared helpers for the Cinder City leaderboard.
declare(strict_types=1);

const CC_LEVELS = 5;
// Plausibility limits. The game cannot change these: they live only here.
const CC_MIN_LEVEL_S   = 25;    // nobody finishes a level faster than this
const CC_MAX_SPEED     = 12.0;  // metres per second: the Free Runner sprints at 9.6, a little faster downhill
const CC_KILLS_BASE    = 90;    // most zombies a level starts with, plus slack
const CC_KILLS_PER_S   = 0.25;  // new zombies arrive at most this fast
const CC_CLOCK_SLACK_S = 8;     // reported play time may be this much ahead of the server clock
const CC_MAX_RUN_S     = 6 * 3600;

function cc_config(): array {
  static $c = null;
  if ($c === null) {
    $f = __DIR__ . '/config.php';
    if (!is_file($f)) cc_fail(503, 'not configured');
    $c = require $f;
  }
  return $c;
}

function cc_db(): PDO {
  static $db = null;
  if ($db === null) {
    $c = cc_config();
    try {
      $db = new PDO('mysql:host=' . $c['db_host'] . ';dbname=' . $c['db_name'] . ';charset=utf8mb4', $c['db_user'], $c['db_pass'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
      ]);
    } catch (Throwable $e) {
      cc_fail(503, 'database unavailable');
    }
  }
  return $db;
}

function cc_json(array $data, int $code = 200): void {
  http_response_code($code);
  header('Content-Type: application/json; charset=utf-8');
  header('Cache-Control: no-store');
  header('X-Content-Type-Options: nosniff');
  echo json_encode($data, JSON_UNESCAPED_UNICODE);
  exit;
}

function cc_fail(int $code, string $msg): void {
  cc_json(['ok' => false, 'error' => $msg], $code);
}

// JSON body of a POST request, at most 2 kB
function cc_body(): array {
  if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') cc_fail(405, 'POST only');
  $raw = file_get_contents('php://input', false, null, 0, 2048);
  $d = json_decode($raw === false ? '' : $raw, true);
  if (!is_array($d)) cc_fail(400, 'bad request');
  return $d;
}

function cc_ip_hash(): string {
  return hash_hmac('sha256', $_SERVER['REMOTE_ADDR'] ?? '', cc_config()['secret']);
}

function cc_token(string $run): string {
  return hash_hmac('sha256', 'run:' . $run, cc_config()['secret']);
}

// counts this request and stops it if the address has made too many of the same kind in the last hour
function cc_rate(string $act, int $max): void {
  $db = cc_db(); $ip = cc_ip_hash(); $now = time();
  $q = $db->prepare('SELECT COUNT(*) FROM cc_hits WHERE ip_hash = ? AND act = ? AND t > ?');
  $q->execute([$ip, $act, $now - 3600]);
  if ((int)$q->fetchColumn() >= $max) cc_fail(429, 'too many requests');
  $db->prepare('INSERT INTO cc_hits (ip_hash, act, t) VALUES (?, ?, ?)')->execute([$ip, $act, $now]);
}

// now and then: forget old tickets and rate-limit rows
function cc_cleanup(): void {
  if (random_int(1, 50) !== 1) return;
  $db = cc_db(); $now = time();
  $db->prepare('DELETE FROM cc_hits WHERE t < ?')->execute([$now - 86400]);
  $db->prepare('DELETE FROM cc_runs WHERE started_at < ?')->execute([$now - 3 * 86400]);
}

function cc_int($v, int $max): int {
  if (!is_int($v) && !is_float($v) && !(is_string($v) && is_numeric($v))) return 0;
  $n = (int)round((float)$v);
  return max(0, min($max, $n));
}

// letters, digits, space and - _ . only; at most 12 characters; '' if nothing is left
function cc_name($v): string {
  if (!is_string($v)) return '';
  $s = preg_replace('/[^\p{L}\p{N} _\-.]/u', '', $v) ?? '';
  $s = trim(preg_replace('/\s+/u', ' ', $s) ?? '');
  $s = mb_substr($s, 0, 12, 'UTF-8');
  if ($s === '') return '';
  $low = mb_strtolower($s, 'UTF-8');
  foreach (cc_config()['badwords'] ?? [] as $w) {
    if ($w !== '' && mb_strpos($low, mb_strtolower((string)$w, 'UTF-8')) !== false) return 'Survivor';
  }
  return $s;
}

function cc_chr($v): string {
  return $v === 'parkour' ? 'Free Runner' : ($v === 'brand' ? 'Firefighter' : '');
}

// Loads the run a request belongs to, after checking its ticket.
function cc_run(array $d): array {
  $run = $d['run'] ?? ''; $tok = $d['token'] ?? '';
  if (!is_string($run) || !is_string($tok) || !preg_match('/^[0-9a-f]{32}$/', $run)) cc_fail(400, 'bad ticket');
  if (!hash_equals(cc_token($run), $tok)) cc_fail(403, 'bad ticket');
  $q = cc_db()->prepare('SELECT * FROM cc_runs WHERE id = ?');
  $q->execute([$run]);
  $r = $q->fetch();
  if (!$r) cc_fail(404, 'unknown ticket');
  return $r;
}

// Checks reported totals against the previous report and the server clock.
// Returns '' when everything is plausible, otherwise a short note saying which rule broke.
function cc_check(array $r, int $time, int $kills, int $dist, bool $levelDone): string {
  $now = time();
  $dt = $time - (int)$r['time_s']; $dk = $kills - (int)$r['kills']; $dd = $dist - (int)$r['dist_m'];
  if ($dt < 0 || $dk < 0 || $dd < 0) return 'totals went down';
  if ($time > $now - (int)$r['started_at'] + CC_CLOCK_SLACK_S) return 'play time ahead of the clock';
  if ($dt > $now - (int)$r['last_at'] + CC_CLOCK_SLACK_S) return 'level time ahead of the clock';
  if ($now - (int)$r['started_at'] > CC_MAX_RUN_S) return 'run too old';
  if ($levelDone && $dt < CC_MIN_LEVEL_S) return 'level finished too fast';
  if ($dd > $dt * CC_MAX_SPEED + 30) return 'moved too fast';
  if ($dk > CC_KILLS_BASE + $dt * CC_KILLS_PER_S) return 'too many kills';
  return '';
}
