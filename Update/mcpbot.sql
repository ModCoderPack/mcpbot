BEGIN;


CREATE TABLE classes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  side INT NOT NULL,
  name TEXT NOT NULL,
  notch TEXT,
  superid INT,
  topsuperid INT,
  isinterf INT NOT NULL,
  packageid INT NOT NULL,
  versionid INT NOT NULL,
  FOREIGN KEY(superid) REFERENCES classes(id),
  FOREIGN KEY(topsuperid) REFERENCES classes(id),
  FOREIGN KEY(packageid) REFERENCES packages(id),
  FOREIGN KEY(versionid) REFERENCES versions(id)
);


CREATE TABLE commits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp INTEGER NOT NULL,
  nick TEXT NOT NULL
);


CREATE TABLE config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  value TEXT NOT NULL,
  UNIQUE(name)
);

INSERT INTO config VALUES(1, 'currentversion', -1);


CREATE TABLE fields (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  side INT NOT NULL,
  searge TEXT NOT NULL,
  notch TEXT,
  name TEXT,
  sig TEXT NOT NULL,
  notchsig TEXT,
  desc TEXT,
  topid INT,
  dirtyid INT NOT NULL DEFAULT 0,
  versionid INT NOT NULL,
  FOREIGN KEY(topid) REFERENCES classes(id),
  FOREIGN KEY(versionid) REFERENCES versions(id)
);


CREATE TABLE fieldshist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memberid INT NOT NULL,
  oldname TEXT NOT NULL,
  olddesc TEXT NOT NULL,
  newname TEXT NOT NULL,
  newdesc TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  nick TEXT NOT NULL,
  forced INT NOT NULL,
  cmd TEXT NOT NULL,
  FOREIGN KEY(memberid) REFERENCES fields(id)
);


CREATE TABLE fieldslk (
  memberid INT NOT NULL,
  classid INT NOT NULL,
  UNIQUE(memberid, classid),
  FOREIGN KEY(memberid) REFERENCES fields(id),
  FOREIGN KEY(classid) REFERENCES classes(id)
);


CREATE TABLE interfaceslk (
  classid INT NOT NULL,
  interfid INT NOT NULL,
  UNIQUE(classid, interfid),
  FOREIGN KEY(classid) REFERENCES classes(id),
  FOREIGN KEY(interfid) REFERENCES classes(id)
);


CREATE TABLE methods (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  side INT NOT NULL,
  searge TEXT NOT NULL,
  notch TEXT,
  name TEXT,
  sig TEXT NOT NULL,
  notchsig TEXT,
  desc TEXT,
  topid INT,
  dirtyid INT NOT NULL DEFAULT 0,
  versionid INT NOT NULL,
  FOREIGN KEY(topid) REFERENCES classes(id),
  FOREIGN KEY(versionid) REFERENCES versions(id)
);


CREATE TABLE methodshist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memberid INT NOT NULL,
  oldname TEXT NOT NULL,
  olddesc TEXT NOT NULL,
  newname TEXT NOT NULL,
  newdesc TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  nick TEXT NOT NULL,
  forced INT NOT NULL,
  cmd TEXT NOT NULL,
  FOREIGN KEY(memberid) REFERENCES methods(id)
);


CREATE TABLE methodslk (
  memberid INT NOT NULL,
  classid INT NOT NULL,
  UNIQUE(memberid, classid),
  FOREIGN KEY(memberid) REFERENCES methods(id),
  FOREIGN KEY(classid) REFERENCES classes(id)
);


CREATE TABLE packages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  UNIQUE(name)
);


CREATE TABLE versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mcpversion TEXT NOT NULL,
  botversion TEXT NOT NULL,
  dbversion TEXT NOT NULL,
  clientversion TEXT NOT NULL,
  serverversion TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  UNIQUE(mcpversion, botversion, dbversion, clientversion, serverversion)
);


CREATE VIEW vclasses AS
  SELECT c.id,
    c.side,
    c.name,
    c.notch,
    c1.name AS supername,
    c.isinterf,
    p.name AS package,
    c.versionid
  FROM classes c
    INNER JOIN packages p ON c.packageid=p.id
    LEFT JOIN classes c1 ON c.superid=c1.id;


CREATE VIEW vclassesstats AS
  SELECT c.id,
    c.name,
    c.side,
    c.versionid,
    COUNT(DISTINCT mt.id) AS methodst,
    COUNT(DISTINCT ft.id) AS fieldst,
    COUNT(DISTINCT mr.id) AS methodsr,
    COUNT(DISTINCT fr.id) AS fieldsr,
    COUNT(DISTINCT mu.id) AS methodsu,
    COUNT(DISTINCT fu.id) AS fieldsu
  FROM classes c
    INNER JOIN packages p ON p.id=c.packageid AND p.name LIKE "net/minecraft/%"
    LEFT JOIN methods mt ON mt.topid=c.id AND mt.searge LIKE "func_%"
    LEFT JOIN methods mr ON mr.id=mt.id AND mr.searge LIKE "func_%" AND mr.name != mr.searge
    LEFT JOIN methods mu ON mu.id=mt.id AND mu.searge LIKE "func_%" AND mu.name = mu.searge
    LEFT JOIN fields ft ON ft.topid=c.id AND ft.searge LIKE "field_%"
    LEFT JOIN fields fr ON fr.id=ft.id AND fr.searge LIKE "field_%" AND fr.name != fr.searge
    LEFT JOIN fields fu ON fu.id=ft.id AND fu.searge LIKE "field_%" AND fu.name = fu.searge
  GROUP BY c.id;


CREATE VIEW vconstructors AS
  SELECT m.id,
    m.side,
    m.name,
    m.notch,
    m.sig,
    m.notchsig,
    m.versionid
  FROM methods m
    INNER JOIN classes c ON m.name=c.name AND m.side=c.side AND m.versionid=c.versionid;


CREATE VIEW vfields AS
  SELECT m.id,
    m.side,
    m.searge,
    m.notch,
    CASE WHEN m.dirtyid > 0 THEN h.newname ELSE m.name END AS name,
    m.name AS oldname,
    CASE WHEN m.dirtyid > 0 THEN h.newdesc ELSE m.desc END AS desc,
    m.desc AS olddesc,
    m.sig,
    m.notchsig,
    c.name AS classname,
    c.notch AS classnotch,
    p.name AS package,
    c.versionid,
    h.forced,
    h.cmd,
    h.nick
  FROM fields m
    INNER JOIN classes c ON m.topid=c.id
    INNER JOIN packages p ON c.packageid=p.id
    LEFT JOIN fieldshist h ON m.dirtyid=h.id;


CREATE VIEW vfieldsall AS
  SELECT m.id,
    m.side,
    m.searge,
    m.notch,
    CASE WHEN m.dirtyid > 0 THEN h.newname ELSE m.name END AS name,
    m.name AS oldname,
    CASE WHEN m.dirtyid > 0 THEN h.newdesc ELSE m.desc END AS desc,
    m.desc AS olddesc,
    m.sig,
    m.notchsig,
    c.name AS classname,
    c.notch AS classnotch,
    c1.name AS topname,
    c1.notch AS topnotch,
    p.name AS package,
    c.versionid,
    h.forced,
    h.cmd,
    h.nick
  FROM fields m
    INNER JOIN fieldslk mlk ON mlk.memberid=m.id
    INNER JOIN classes c ON mlk.classid=c.id
    INNER JOIN classes c1 ON m.topid=c1.id
    INNER JOIN packages p ON c.packageid=p.id
    LEFT JOIN fieldshist h ON m.dirtyid=h.id;


CREATE VIEW vmethods AS
  SELECT m.id,
    m.side,
    m.searge,
    m.notch,
    CASE WHEN m.dirtyid > 0 THEN h.newname ELSE m.name END AS name,
    m.name AS oldname,
    CASE WHEN m.dirtyid > 0 THEN h.newdesc ELSE m.desc END AS desc,
    m.desc AS olddesc,
    m.sig,
    m.notchsig,
    c.name AS classname,
    c.notch AS classnotch,
    p.name AS package,
    c.versionid,
    h.forced,
    h.cmd,
    h.nick
  FROM methods m
    INNER JOIN classes c ON m.topid=c.id
    INNER JOIN packages p ON c.packageid=p.id
    LEFT JOIN methodshist h ON m.dirtyid=h.id;


CREATE VIEW vmethodsall AS
  SELECT m.id,
    m.side,
    m.searge,
    m.notch,
    CASE WHEN m.dirtyid > 0 THEN h.newname ELSE m.name END AS name,
    m.name AS oldname,
    CASE WHEN m.dirtyid > 0 THEN h.newdesc ELSE m.desc END AS desc,
    m.desc AS olddesc,
    m.sig,
    m.notchsig,
    c.name AS classname,
    c.notch AS classnotch,
    c1.name AS topname,
    c1.notch AS topnotch,
    p.name AS package,
    c.versionid,
    h.forced,
    h.cmd,
    h.nick
  FROM methods m
    INNER JOIN methodslk mlk ON mlk.memberid=m.id
    INNER JOIN classes c ON mlk.classid=c.id
    INNER JOIN classes c1 ON m.topid=c1.id
    INNER JOIN packages p ON c.packageid=p.id
    LEFT JOIN methodshist h ON m.dirtyid=h.id;


CREATE TRIGGER update_fields_dirty AFTER INSERT ON fieldshist BEGIN
  UPDATE fields SET dirtyid=new.id
    WHERE id=new.memberid;
END;


CREATE TRIGGER update_methods_dirty AFTER INSERT ON methodshist BEGIN
  UPDATE methods SET dirtyid=new.id
    WHERE id=new.memberid;
END;


CREATE INDEX classes_isinterf_idx ON classes(isinterf);
CREATE INDEX classes_name_idx ON classes(name);
CREATE INDEX classes_notch_idx ON classes(notch);
CREATE INDEX classes_packageid_idx ON classes(packageid);
CREATE INDEX classes_side_idx ON classes(side);
CREATE INDEX classes_superid_idx ON classes(superid);
CREATE INDEX classes_topsuperid_idx ON classes(topsuperid);
CREATE INDEX classes_versionid_idx ON classes(versionid);

CREATE INDEX fields_dirtyid_idx ON fields(dirtyid);
CREATE INDEX fields_notch_idx ON fields(notch);
CREATE INDEX fields_notchsig_idx ON fields(notchsig);
CREATE INDEX fields_searge_idx ON fields(searge);
CREATE INDEX fields_side_idx ON fields(side);
CREATE INDEX fields_sig_idx ON fields(sig);
CREATE INDEX fields_topid_idx ON fields(topid);
CREATE INDEX fields_versionid_idx ON fields(versionid);

CREATE INDEX fieldshist_memberid_idx ON fieldshist(memberid);

CREATE INDEX fieldslk_classid_idx ON fieldslk(classid);
CREATE INDEX fieldslk_memberid_idx ON fieldslk(memberid);

CREATE INDEX interfaceslk_classid_idx ON interfaceslk(classid);
CREATE INDEX interfaceslk_interfid_idx ON interfaceslk(interfid);

CREATE INDEX methods_dirtyid_idx ON methods(dirtyid);
CREATE INDEX methods_notch_idx ON methods(notch);
CREATE INDEX methods_notchsig_idx ON methods(notchsig);
CREATE INDEX methods_searge_idx ON methods(searge);
CREATE INDEX methods_side_idx ON methods(side);
CREATE INDEX methods_sig_idx ON methods(sig);
CREATE INDEX methods_topid_idx ON methods(topid);
CREATE INDEX methods_versionid_idx ON methods(versionid);

CREATE INDEX methodshist_memberid_idx ON methodshist(memberid);

CREATE INDEX methodslk_classid_idx ON methodslk(classid);
CREATE INDEX methodslk_memberid_idx ON methodslk(memberid);

COMMIT;
