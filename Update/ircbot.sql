BEGIN;


CREATE TABLE cmdshist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nickid INTEGER NOT NULL,
  cmd TEXT NOT NULL,
  params TEXT,
  timestamp INTEGER NOT NULL,
  FOREIGN KEY(nickid) REFERENCES nicks(id)
);


CREATE TABLE commands (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cmd TEXT NOT NULL
);


CREATE TABLE groupcmdlk (
  groupid INT NOT NULL,
  cmdid INT NOT NULL,
  UNIQUE(groupid, cmdid),
  FOREIGN KEY(groupid) REFERENCES groups(id),
  FOREIGN KEY(cmdid) REFERENCES commands(id)
);


CREATE TABLE groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name INTEGER NOT NULL,
  UNIQUE(name)
);


CREATE TABLE logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  cmd TEXT NOT NULL,
  sender TEXT NOT NULL,
  target TEXT,
  msg TEXT,
  timestamp INTEGER NOT NULL
);


CREATE TABLE nicks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nick TEXT NOT NULL,
  user TEXT,
  host TEXT,
  timestamp INTEGER NOT NULL,
  online INTEGER NOT NULL,
  UNIQUE(nick)
);


CREATE TABLE notices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  tag TEXT NOT NULL,
  content TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  nickid INTEGER NOT NULL,
  FOREIGN KEY(nickid) REFERENCES nicks(id)
);


CREATE TABLE usercmdlk (
  userid INT NOT NULL,
  cmdid INT NOT NULL,
  UNIQUE(userid, cmdid),
  FOREIGN KEY(userid) REFERENCES nicks(id),
  FOREIGN KEY(cmdid) REFERENCES commands(id)
);


CREATE TABLE usergrouplk (
  userid INT NOT NULL,
  groupid INT NOT NULL,
  UNIQUE(userid, groupid),
  FOREIGN KEY(userid) REFERENCES users(id),
  FOREIGN KEY(groupid) REFERENCES groups(id)
);


COMMIT;
