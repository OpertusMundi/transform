DROP TABLE IF EXISTS tickets;

CREATE TABLE tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket TEXT NOT NULL,
  status INTEGER DEFAULT 0,
  success INTEGER,
  execution_time REAL,
  requested_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  result text,
  filesize INTEGER,
  comment text
);

CREATE UNIQUE INDEX idx_tickets_ticket
ON tickets (ticket);
