<?php
// Cinder City leaderboard API.  ?a=top (GET) · ?a=start · ?a=level · ?a=submit (POST, JSON)
declare(strict_types=1);
require __DIR__ . '/lib.php';

$a = $_GET['a'] ?? '';

try {
  if ($a === 'top') {
    $db = cc_db();
    // best result per name in each list; the fastest list only holds finished campaigns
    $lists = [
      'time'  => 'SELECT name, MIN(time_s) AS v, SUBSTRING_INDEX(GROUP_CONCAT(chr ORDER BY time_s ASC), \',\', 1) AS chr
                  FROM cc_scores WHERE hidden = 0 AND finished = 1 GROUP BY name ORDER BY v ASC LIMIT 20',
      'kills' => 'SELECT name, MAX(kills) AS v, SUBSTRING_INDEX(GROUP_CONCAT(chr ORDER BY kills DESC), \',\', 1) AS chr
                  FROM cc_scores WHERE hidden = 0 GROUP BY name ORDER BY v DESC LIMIT 20',
      'dist'  => 'SELECT name, MAX(dist_m) AS v, SUBSTRING_INDEX(GROUP_CONCAT(chr ORDER BY dist_m DESC), \',\', 1) AS chr
                  FROM cc_scores WHERE hidden = 0 GROUP BY name ORDER BY v DESC LIMIT 20',
    ];
    $out = ['ok' => true];
    foreach ($lists as $k => $sql) {
      $rows = [];
      foreach ($db->query($sql) as $row) $rows[] = ['name' => $row['name'], 'chr' => $row['chr'], 'v' => (int)$row['v']];
      $out[$k] = $rows;
    }
    cc_json($out);
  }

  if ($a === 'visit') { // internal visitor count: one row per address and day, n = page loads
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') cc_fail(405, 'POST only');
    cc_visit();
    cc_json(['ok' => true]);
  }

  if ($a === 'start') {
    $d = cc_body();
    $c = cc_config();
    cc_rate('start', (int)($c['max_starts_per_hour'] ?? 40));
    cc_cleanup();
    $run = bin2hex(random_bytes(16)); $now = time();
    cc_db()->prepare('INSERT INTO cc_runs (id, ip_hash, chr, started_at, last_at) VALUES (?, ?, ?, ?, ?)')
      ->execute([$run, cc_ip_hash(), cc_chr($d['chr'] ?? ''), $now, $now]);
    cc_json(['ok' => true, 'run' => $run, 'token' => cc_token($run)]);
  }

  if ($a === 'level') { // a level was finished: totals so far
    $d = cc_body();
    $r = cc_run($d);
    $level = cc_int($d['level'] ?? 0, 99);
    $time = cc_int($d['time'] ?? 0, 999999); $kills = cc_int($d['kills'] ?? 0, 999999); $dist = cc_int($d['dist'] ?? 0, 9999999);
    $note = '';
    if ($level !== (int)$r['levels_done'] + 1 || $level > CC_LEVELS) $note = 'levels out of order';
    else $note = cc_check($r, $time, $kills, $dist, true);
    if ($note !== '') {
      cc_db()->prepare('UPDATE cc_runs SET flagged = 1, flag_note = ? WHERE id = ?')->execute([$note, $r['id']]);
    } else {
      cc_db()->prepare('UPDATE cc_runs SET levels_done = ?, time_s = ?, kills = ?, dist_m = ?, last_at = ? WHERE id = ?')
        ->execute([$level, $time, $kills, $dist, time(), $r['id']]);
    }
    cc_json(['ok' => true]); // a broken rule is not reported back
  }

  if ($a === 'submit') { // the game ended (all levels done, or the crew is gone): put the run on the board
    $d = cc_body();
    $r = cc_run($d);
    $c = cc_config();
    $name = cc_name($d['name'] ?? '');
    if ($name === '') $name = 'Unnamed' . random_int(1000, 9999); // the game saves every run at the end, before the player has typed a name
    cc_rate('submit', (int)($c['max_submits_per_hour'] ?? 20));
    $time = cc_int($d['time'] ?? 0, 999999); $kills = cc_int($d['kills'] ?? 0, 999999); $dist = cc_int($d['dist'] ?? 0, 9999999);
    $finished = (int)$r['levels_done'] >= CC_LEVELS;
    $note = (int)$r['flagged'] ? (string)$r['flag_note'] : '';
    if ($finished) { // a finished campaign is scored on what the last level report said
      $time = (int)$r['time_s']; $kills = (int)$r['kills']; $dist = (int)$r['dist_m'];
    } elseif ($note === '') {
      $note = cc_check($r, $time, $kills, $dist, false);
    }
    $hidden = $note === '' ? 0 : 1;
    cc_db()->prepare('INSERT INTO cc_scores (run_id, name, chr, finished, time_s, kills, dist_m, hidden, note, ip_hash, created_at)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                      ON DUPLICATE KEY UPDATE name = VALUES(name), finished = VALUES(finished), time_s = VALUES(time_s), kills = VALUES(kills),
                        dist_m = VALUES(dist_m), hidden = GREATEST(hidden, VALUES(hidden)), note = VALUES(note)')
      ->execute([$r['id'], $name, $r['chr'], $finished ? 1 : 0, $time, $kills, $dist, $hidden, $note, cc_ip_hash(), time()]);
    cc_db()->prepare('UPDATE cc_runs SET time_s = GREATEST(time_s, ?), kills = GREATEST(kills, ?), dist_m = GREATEST(dist_m, ?), last_at = ? WHERE id = ?')
      ->execute([$time, $kills, $dist, time(), $r['id']]);
    cc_json(['ok' => true, 'name' => $name, 'finished' => $finished]);
  }

  cc_fail(404, 'unknown action');
} catch (Throwable $e) {
  error_log('cinder-city api: ' . $e->getMessage());
  cc_fail(500, 'server error');
}
