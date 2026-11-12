-- 独立审核库内执行；不涉及PostgreSQL、原始文件或解析任务库。
CREATE TABLE review_meta (
  singleton TINYINT PRIMARY KEY,
  schema_version INT NOT NULL
) ENGINE=InnoDB;
INSERT INTO review_meta VALUES (1,1);
CREATE TABLE review_heads (
  owner_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  parse_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  version INT UNSIGNED NOT NULL,
  status VARCHAR(16) NOT NULL,
  current_revision CHAR(36) NULL,
  source_digest CHAR(64) NOT NULL,
  PRIMARY KEY(owner_key,parse_id)
) ENGINE=InnoDB;
CREATE TABLE review_events (
  event_id CHAR(36) PRIMARY KEY,
  owner_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  parse_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  version INT UNSIGNED NOT NULL,
  request_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fingerprint CHAR(64) NOT NULL,
  receipt JSON NOT NULL,
  payload JSON NOT NULL,
  UNIQUE KEY owner_request(owner_key,request_key),
  UNIQUE KEY object_version(owner_key,parse_id,version),
  FOREIGN KEY(owner_key,parse_id) REFERENCES review_heads(owner_key,parse_id)
) ENGINE=InnoDB;
