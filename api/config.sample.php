<?php
// Copy this file to config.php (same folder) and fill it in. config.php must never be put in git.
return [
  'db_host' => 'localhost',
  'db_name' => 'your_database',
  'db_user' => 'your_user',
  'db_pass' => 'your_password',

  // Any long random text. It signs the game tickets and hashes IP addresses. Keep it secret; changing it
  // makes games that are in progress unable to post a score.
  'secret' => 'CHANGE-ME-to-a-long-random-string',

  // Password for admin.php. The admin page stays locked until you change it.
  'admin_password' => 'CHANGE-ME',

  // Names containing any of these (upper or lower case) are replaced by "Survivor".
  'badwords' => ['fuck', 'shit', 'nazi', 'hitler', 'sex'],

  // Limits per IP address and hour.
  'max_starts_per_hour'  => 40,
  'max_submits_per_hour' => 20,
];
