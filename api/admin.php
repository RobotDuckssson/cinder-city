<?php
// Cinder City leaderboard admin: look at the latest scores, hide or delete them.
declare(strict_types=1);
require __DIR__ . '/lib.php';

header('Content-Type: text/html; charset=utf-8');
header('X-Frame-Options: DENY');
header('Referrer-Policy: no-referrer');
header('Cache-Control: no-store');
session_set_cookie_params(['httponly' => true, 'samesite' => 'Strict', 'secure' => !empty($_SERVER['HTTPS'])]);
session_name('cc_admin');
session_start();

function h($s): string { return htmlspecialchars((string)$s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function page(string $body): void {
  echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    . '<meta name="robots" content="noindex"><title>Cinder City admin</title><style>'
    . 'body{font:14px/1.5 system-ui,sans-serif;background:#111;color:#ddd;margin:20px}a{color:#f0a33a}'
    . 'table{border-collapse:collapse;width:100%}td,th{padding:5px 8px;border-bottom:1px solid #333;text-align:left;white-space:nowrap}'
    . 'tr.hid td{color:#777}button,input{font:inherit;padding:4px 10px}form{display:inline}.note{color:#e5a03d}'
    . '</style></head><body>' . $body . '</body></html>';
  exit;
}

$c = cc_config();
$pw = (string)($c['admin_password'] ?? '');
if ($pw === '' || $pw === 'CHANGE-ME') page('<p>The admin page is locked: set <code>admin_password</code> in <code>config.php</code> first.</p>');

if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(16));
$csrf = $_SESSION['csrf'];
$post = ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST';
if ($post && !hash_equals($csrf, (string)($_POST['csrf'] ?? ''))) { http_response_code(400); page('<p>The form has expired. <a href="admin.php">Reload</a></p>'); }

if ($post && isset($_POST['logout'])) { $_SESSION = []; session_destroy(); header('Location: admin.php'); exit; }

if (empty($_SESSION['admin'])) {
  $err = '';
  if ($post && isset($_POST['password'])) {
    cc_rate('admin', 10); // at most ten attempts per hour and address
    if (hash_equals($pw, (string)$_POST['password'])) { session_regenerate_id(true); $_SESSION['admin'] = 1; header('Location: admin.php'); exit; }
    sleep(1); $err = '<p class="note">Wrong password.</p>';
  }
  page('<h2>Cinder City admin</h2>' . $err . '<form method="post"><input type="hidden" name="csrf" value="' . h($csrf) . '">'
    . '<input type="password" name="password" placeholder="Password" autofocus> <button>Log in</button></form>');
}

$db = cc_db();
if ($post && isset($_POST['id'], $_POST['do'])) {
  $id = (int)$_POST['id'];
  if ($_POST['do'] === 'hide') $db->prepare('UPDATE cc_scores SET hidden = 1 WHERE id = ?')->execute([$id]);
  if ($_POST['do'] === 'show') $db->prepare('UPDATE cc_scores SET hidden = 0 WHERE id = ?')->execute([$id]);
  if ($_POST['do'] === 'delete') $db->prepare('DELETE FROM cc_scores WHERE id = ?')->execute([$id]);
  if ($_POST['do'] === 'hideall') { // everything from the same address as this score
    $q = $db->prepare('UPDATE cc_scores s JOIN cc_scores t ON t.ip_hash = s.ip_hash SET s.hidden = 1 WHERE t.id = ?');
    $q->execute([$id]);
  }
  header('Location: admin.php?show=' . urlencode((string)($_GET['show'] ?? ''))); exit;
}

$show = (string)($_GET['show'] ?? '');
$where = $show === 'hidden' ? 'WHERE hidden = 1' : '';
$rows = $db->query("SELECT * FROM cc_scores $where ORDER BY created_at DESC LIMIT 300")->fetchAll();
$tot = $db->query('SELECT COUNT(*) AS n, SUM(hidden) AS h FROM cc_scores')->fetch();

$btn = function (int $id, string $do, string $label) use ($csrf): string {
  $conf = $do === 'delete' || $do === 'hideall' ? ' onclick="return confirm(\'' . h($label) . '?\')"' : '';
  return '<form method="post"><input type="hidden" name="csrf" value="' . h($csrf) . '"><input type="hidden" name="id" value="' . $id . '">'
    . '<button name="do" value="' . h($do) . '"' . $conf . '>' . h($label) . '</button></form> ';
};
// visitors: unique addresses and page loads, per day for the last 30 days
$vis = ''; $vt = ['u' => 0, 'n' => 0];
try {
  $vrows = $db->query('SELECT day, COUNT(*) AS u, SUM(n) AS n FROM cc_visits WHERE day >= CURDATE() - INTERVAL 29 DAY GROUP BY day ORDER BY day DESC')->fetchAll();
  $vt = $db->query('SELECT COUNT(DISTINCT ip_hash) AS u, SUM(n) AS n FROM cc_visits')->fetch();
  $vis = '<h3>Visitors</h3><p>All time: ' . (int)$vt['u'] . ' different visitors, ' . (int)$vt['n'] . ' page loads.</p>'
    . '<table style="width:auto"><tr><th>Day</th><th>Visitors</th><th>Page loads</th></tr>';
  foreach ($vrows as $v) $vis .= '<tr><td>' . h($v['day']) . '</td><td>' . (int)$v['u'] . '</td><td>' . (int)$v['n'] . '</td></tr>';
  $vis .= '</table><h3>Scores</h3>';
} catch (Throwable $e) { $vis = '<h3>Visitors</h3><p>No visits counted yet.</p><h3>Scores</h3>'; }

$fmt = function (int $s): string { return sprintf('%d:%02d', intdiv($s, 60), $s % 60); };

$b = '<h2>Cinder City admin</h2><p>' . (int)$tot['n'] . ' scores, ' . (int)$tot['h'] . ' hidden. '
  . '<a href="admin.php">Latest</a> · <a href="admin.php?show=hidden">Hidden only</a> '
  . '<form method="post"><input type="hidden" name="csrf" value="' . h($csrf) . '"><button name="logout" value="1">Log out</button></form></p>'
  . $vis . '<table><tr><th>When</th><th>Name</th><th>Character</th><th>Finished</th><th>Time</th><th>Kills</th><th>Distance</th><th>Address</th><th>Note</th><th></th></tr>';
foreach ($rows as $r) {
  $id = (int)$r['id'];
  $b .= '<tr class="' . ($r['hidden'] ? 'hid' : '') . '"><td>' . h(date('Y-m-d H:i', (int)$r['created_at'])) . '</td><td>' . h($r['name']) . '</td><td>' . h($r['chr']) . '</td>'
    . '<td>' . ($r['finished'] ? 'yes' : 'no') . '</td><td>' . h($fmt((int)$r['time_s'])) . '</td><td>' . (int)$r['kills'] . '</td><td>' . (int)$r['dist_m'] . ' m</td>'
    . '<td>' . h(substr((string)$r['ip_hash'], 0, 8)) . '</td><td class="note">' . h($r['note']) . '</td><td>'
    . ($r['hidden'] ? $btn($id, 'show', 'Show') : $btn($id, 'hide', 'Hide')) . $btn($id, 'hideall', 'Hide all from this address') . $btn($id, 'delete', 'Delete')
    . '</td></tr>';
}
$b .= '</table>';
page($b);
