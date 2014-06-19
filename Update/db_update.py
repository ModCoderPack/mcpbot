import argparse
import sqlite3
import os
import time
import csv
from contextlib import contextmanager, closing

from pjp.classfile import ClassFile
from pjp.jarfile import JarFile

SIDE_LOOKUP = {'client': 0, 'server': 1}


def parse_srg(srg_filename):
    srg_types = {'CL:': ['name_o', 'name_d'],
                 'FD:': ['name_o', 'name_d'],
                 'MD:': ['name_o', 'sig_o', 'name_d', 'sig_d'],
                 'PK:': ['name_o', 'name_d']}
    parsed_dict = {'CL': [],
                   'FD': [],
                   'MD': [],
                   'PK': []}

    def get_parsed_line(keyword, buf):
        return dict(zip(srg_types[keyword], [i.strip() for i in buf]))

    with open(srg_filename, 'r') as srg_file:
        for buf in srg_file:
            buf = buf.strip()
            if buf == '' or buf[0] == '#':
                continue
            buf = buf.split()
            parsed_dict[buf[0][:2]].append(get_parsed_line(buf[0], buf[1:]))
    return parsed_dict


@contextmanager
def get_db(db_name):
    db = sqlite3.connect(db_name, isolation_level=None)
    db.text_factory = sqlite3.OptimizedUnicode
    db.row_factory = sqlite3.Row
#    db.execute("PRAGMA foreign_keys = ON")
    try:
        db.execute("BEGIN IMMEDIATE TRANSACTION")
        yield db
        db.execute("COMMIT TRANSACTION")
    except BaseException as exc:
        try:
            db.execute("ROLLBACK TRANSACTION")
        except sqlite3.Error:
            pass
        raise exc


def strip_sig(sig):
    sig = sig.replace('net/minecraft/src/', '')
    sig = sig.replace('net/minecraft/isom/', '')
    sig = sig.replace('net/minecraft/server/', '')
    sig = sig.replace('net/minecraft/client/', '')
    return sig


def import_jar(db, side, version_id, datapath):
    classes = {}
    class_ids = {}
    members_list = {'fields': {}, 'methods': {}}

    with closing(db.cursor()) as cur:
        # precache package names
        package_list = {}
        query = """
            SELECT id AS package_id, name
            FROM packages
        """
        cur.execute(query)
        rows = cur.fetchall()
        for row in rows:
            package_list[row['name']] = row['package_id']

        # Here we read all the class files
        jar = JarFile(os.path.join(datapath, '%s_recomp.jar' % side))
        for cls in jar.classes:
            class_ = ClassFile(jar[cls])
            # ignore sound classes
            if class_.package_name.startswith('com/jcraft/') or \
               class_.package_name.startswith('paulscode/') or \
               class_.package_name.startswith('org/') or \
               class_.package_name.startswith('com/') or \
               class_.package_name.startswith('argo/'):
                continue
            classes[class_.name] = class_

            if class_.package_name not in package_list:
                query = """
                    INSERT INTO packages (name)
                    VALUES (:name)
                """
                cur.execute(query, {'name': class_.package_name})
                package_id = cur.lastrowid
                package_list[class_.package_name] = package_id
            else:
                package_id = package_list[class_.package_name]

            # We insert the already available informations in the db
            query = """
                INSERT INTO classes (side, name, isinterf, packageid, versionid)
                VALUES (:side, :name, :isinterf, :packageid, :versionid)
            """
            cur.execute(query, {'side': SIDE_LOOKUP[side], 'name': class_.class_name,
                                'isinterf': class_.access_flags.is_interface, 'packageid': package_id,
                                'versionid': version_id})
            class_id = cur.lastrowid
            class_ids[class_.name] = class_id

            for mtype in ['fields', 'methods']:
                for member in getattr(class_, mtype):
                    searge = member.name
                    deobf = None
                    notch = None

                    sig = strip_sig(member.descriptor.value)

                    member_key = searge + '_' + sig
                    if mtype == 'methods':
                        if searge == '<clinit>':
                            # static init
                            continue
                        elif searge == '<init>':
                            # constructor
                            searge = class_.class_name
                            deobf = searge
                            member_key = searge + '_' + sig
                        elif not searge.startswith('func_'):
                            # inherited or already named method
                            deobf = searge
                    else:
                        if not searge.startswith('field_'):
                            # enum field
                            deobf = searge

                    # We insert the member only if it has not be inserted before
                    if member_key not in members_list[mtype]:
                        query = """
                            INSERT INTO {mtype} (side, searge, name, notch, sig, dirtyid, versionid)
                            VALUES (:side, :searge, :name, :notch, :sig, :dirtyid, :versionid)
                        """.format(mtype=mtype)
                        cur.execute(query, {'side': SIDE_LOOKUP[side], 'searge': searge, 'name': deobf, 'notch': notch,
                                            'sig': sig, 'dirtyid': 0, 'versionid': version_id})
                        member_id = cur.lastrowid
                        members_list[mtype][member_key] = member_id
                    else:
                        member_id = members_list[mtype][member_key]

                    # We insert the corresponding key to the memberlk
                    query = """
                        INSERT INTO {mtype}lk (memberid, classid)
                        VALUES (:memberid, :classid)
                    """.format(mtype=mtype)
                    cur.execute(query, {'memberid': member_id, 'classid': class_id})

        for key, class_ in classes.items():
            # We get the super class index and put it in the class entry
            if class_.super_class.name in class_ids:
                query = """
                    UPDATE classes
                    SET superid=:superid
                    WHERE id=:id
                """
                cur.execute(query, {'superid': class_ids[class_.super_class.name], 'id': class_ids[key]})

            # We get the interface ids and insert into interfaceslk
            for interface in class_.interfaces:
                if interface.name in class_ids:
                    query = """
                        INSERT INTO interfaceslk (classid, interfid)
                        VALUES (:classid, :interfid)
                    """
                    cur.execute(query, {'classid': class_ids[key], 'interfid': class_ids[interface.name]})
        cur.execute("ANALYZE")


def import_srg(db, side, version_id, datapath):
    with closing(db.cursor()) as cur:
        mappings = parse_srg(os.path.join(datapath, '%s.srg' % side))
        for class_ in mappings['CL']:
            searge_fullname = class_['name_d']
            searge_package, _, searge_class = searge_fullname.rpartition('/')
            notch_fullname = class_['name_o']
            notch_package, _, notch_class = notch_fullname.rpartition('/')
            query = """
                SELECT c.id AS class_id
                FROM classes c
                  INNER JOIN packages p ON p.id=c.packageid
                WHERE c.notch IS NULL
                  AND c.name=:class AND p.name=:package
                  AND c.side=:side AND c.versionid=:versionid
            """
            cur.execute(query, {'class': searge_class, 'package': searge_package, 'side': SIDE_LOOKUP[side],
                                'versionid': version_id})
            rows = cur.fetchall()
            if len(rows) == 1:
                row = rows[0]
                query = """
                    UPDATE classes
                    SET notch=:notch
                    WHERE id=:id
                """
                cur.execute(query, {'notch': notch_class, 'id': row['class_id']})
            elif len(rows) == 0:
                pass  
            else:
                raise Exception("ERROR: %d classes found for %s %s" % (len(rows), notch_fullname, searge_class))

        # fix Minecraft, MinecraftServer etc. class names that aren't in the RGS
        query = """
            UPDATE classes
            SET notch=name
            WHERE notch IS NULL
              AND side=:side AND versionid=:versionid
        """
        cur.execute(query, {'side': SIDE_LOOKUP[side], 'versionid': version_id})

        for method in mappings['MD']:
            searge_fullname, _, searge_method = method['name_d'].rpartition('/')
            searge_package, _, searge_class = searge_fullname.rpartition('/')
            notch_fullname, _, notch_method = method['name_o'].rpartition('/')
            notch_package, _, notch_class = notch_fullname.rpartition('/')
            searge_sig = strip_sig(method['sig_d'])
            notch_sig = method['sig_o']
            query = """
                SELECT m.id AS method_id, m.notch, m.searge, m.name
                FROM methods m
                  INNER JOIN methodslk l ON l.memberid=m.id
                  INNER JOIN classes c ON c.id=l.classid
                  INNER JOIN packages p ON p.id=c.packageid
                WHERE m.searge=:method AND m.sig=:sig AND c.notch=:class AND p.name=:package
                  AND m.side=:side AND m.versionid=:versionid
                GROUP BY m.id
            """
            cur.execute(query, {'method': searge_method, 'sig': searge_sig, 'class': notch_class,
                                'package': searge_package, 'side': SIDE_LOOKUP[side], 'versionid': version_id})
            rows = cur.fetchall()
            if len(rows) == 1:
                row = rows[0]
                if row['notch'] is None:
                    query = """
                        UPDATE methods
                        SET notch=:notch, notchsig=:notchsig
                        WHERE id=:id
                    """
                    cur.execute(query, {'notch': notch_method, 'notchsig': notch_sig, 'id': row['method_id']})
                elif row['notch'] != notch_method:
                    raise Exception("ERROR: mismatched method found for %s/%s %s %s with %s" % (
                        notch_fullname, notch_method, notch_sig, searge_method, row['notch']))
            elif len(rows) == 0:
                pass                      
            else:
                notch_unset = 0
                for row in rows:
                    if row['notch'] is None:
                        notch_unset += 1
                print Exception("ERROR: %d methods found for %s/%s %s %s " % (
                    notch_unset, notch_fullname, notch_method, notch_sig, searge_method))

        for field in mappings['FD']:
            searge_fullname, _, searge_field = field['name_d'].rpartition('/')
            searge_package, _, searge_class = searge_fullname.rpartition('/')
            notch_fullname, _, notch_field = field['name_o'].rpartition('/')
            notch_package, _, notch_class = notch_fullname.rpartition('/')
            query = """
                SELECT f.id AS field_id, f.notch
                FROM fields f
                  INNER JOIN fieldslk l ON l.memberid=f.id
                  INNER JOIN classes c ON c.id=l.classid
                  INNER JOIN packages p ON p.id=c.packageid
                WHERE f.searge=:field AND c.notch=:class AND p.name=:package
                  AND f.side=:side AND f.versionid=:versionid
                GROUP BY f.id
            """
            cur.execute(query, {'field': searge_field, 'class': notch_class, 'package': searge_package,
                                'side': SIDE_LOOKUP[side], 'versionid': version_id})
            rows = cur.fetchall()
            if len(rows) == 1:
                row = rows[0]
                if row['notch'] is None:
                    query = """
                        UPDATE fields
                        SET notch=:notch
                        WHERE id=:id
                    """
                    cur.execute(query, {'notch': notch_field, 'id': row['field_id']})
                elif row['notch'] != notch_field:
                    raise Exception("ERROR: mismatched field found for %s/%s %s with %s" % (
                        notch_fullname, notch_field, searge_field, row['notch']))
            elif len(rows) == 0:
                pass                      
            else:
                notch_unset = 0
                for row in rows:
                    if row['notch'] is None:
                        notch_unset += 1
                print Exception("ERROR: %d fields found for %s/%s %s" % (
                    notch_unset, notch_fullname, notch_field, searge_field))


def update_misc(db, side, version_id):
    with closing(db.cursor()) as cur:
        # We update all constructors with the notch class name
        query = """
            SELECT m.id AS member_id, c.notch
            FROM methods m
              INNER JOIN methodslk ml ON ml.memberid=m.id
              INNER JOIN classes c ON c.id=ml.classid
            WHERE m.notch IS NULL AND m.searge=c.name
              AND m.side=:side AND m.versionid=:versionid
        """
        cur.execute(query, {'side': SIDE_LOOKUP[side], 'versionid': version_id})
        rows = cur.fetchall()
        for row in rows:
            query = """
                UPDATE methods
                SET notch=:notch
                WHERE id=:id
            """
            cur.execute(query, {'notch': row['notch'], 'id': row['member_id']})

        # We fill all the remaining blanks with searge name
        query = """
            UPDATE methods
            SET notch=searge
            WHERE notch IS NULL
              AND side=:side AND versionid=:versionid
        """
        cur.execute(query, {'side': SIDE_LOOKUP[side], 'versionid': version_id})
        query = """
            UPDATE fields
            SET notch=searge
            WHERE notch IS NULL
              AND side=:side AND versionid=:versionid
        """
        cur.execute(query, {'side': SIDE_LOOKUP[side], 'versionid': version_id})

        for mtype in ['fields', 'methods']:
            print " > Checking %s"%mtype
            # We get all the methods defined in interfaces and set the topid to it.
            query = """
                SELECT c.id AS class_id, m.id AS member_id
                FROM classes c
                  INNER JOIN {mtype}lk lk ON lk.classid=c.id
                  INNER JOIN {mtype} m ON m.id=lk.memberid
                WHERE c.isinterf=:isinterf
                  AND c.side=:side AND c.versionid=:versionid
            """.format(mtype=mtype)
            cur.execute(query, {'isinterf': True, 'side': SIDE_LOOKUP[side], 'versionid': version_id})
            rows = cur.fetchall()
            for row in rows:
                query = """
                    UPDATE {mtype}
                    SET topid=:topid
                    WHERE id=:id
                """.format(mtype=mtype)
                cur.execute(query, {'topid': row['class_id'], 'id': row['member_id']})

            # We get all the methods which are implemented in classes without a super and we set the top id
            query = """
                SELECT c.id AS class_id, m.id AS member_id
                FROM {mtype} m
                  INNER JOIN {mtype}lk ml ON ml.memberid=m.id
                  INNER JOIN classes c ON c.id=ml.classid
                WHERE c.superid IS NULL AND m.topid IS NULL
                  AND m.side=:side AND m.versionid=:versionid
            """.format(mtype=mtype)
            cur.execute(query, {'side': SIDE_LOOKUP[side], 'versionid': version_id})
            rows = cur.fetchall()
            for row in rows:
                query = """
                    UPDATE {mtype}
                    SET topid=:topid
                    WHERE id=:id
                """.format(mtype=mtype)
                cur.execute(query, {'topid': row['class_id'], 'id': row['member_id']})

            # We get all the methods not yet with a top id
            query = """
                SELECT id AS member_id
                FROM {mtype}
                WHERE topid IS NULL
                  AND side=:side AND versionid=:versionid
            """.format(mtype=mtype)
            cur.execute(query, {'side': SIDE_LOOKUP[side], 'versionid': version_id})
            rows = cur.fetchall()
            errors = []
            for mid in rows:
                member_id = mid['member_id']

                # We get all classes for this method. Also, we drop the interfaces.
                # Modification : Interfaces shouldn't be dropped as it will also drop some abstract classes for some reason.
                query = """
                    SELECT c.id AS class_id, c.superid AS super_id, c.name AS cname
                    FROM {mtype} m
                      INNER JOIN {mtype}lk ml ON ml.memberid=m.id
                      INNER JOIN classes c ON c.id=ml.classid
                    WHERE m.id=:memberid AND c.isinterf=:isinterf
                """.format(mtype=mtype)
                #cur.execute(query, {'memberid': member_id, 'isinterf': False})
                cur.execute(query, {'memberid': member_id, 'isinterf': True})
                rows = cur.fetchall()
                classids = [row['class_id'] for row in rows]
                results = []
                cnames  = []
                for row in rows:
                    cnames.append(row['cname'])
                    if not row['super_id'] in classids:
                        results.append(row['class_id'])

                # If we have only one result, this is the top id.
                if len(results) == 1:
                    query = """
                        UPDATE {mtype}
                        SET topid=:topid
                        WHERE id=:id
                    """.format(mtype=mtype)
                    cur.execute(query, {'topid': results[0], 'id': member_id})

                # If we have more than one result, we have to walk the tree
                if len(results) > 1:
                    query = """
                        SELECT id AS class_id, superid AS super_id
                        FROM classes
                        WHERE isinterf=:isinterf
                          AND side=:side AND versionid=:versionid
                    """
                    cur.execute(query, {'isinterf': False, 'side': SIDE_LOOKUP[side], 'versionid': version_id})
                    rows = cur.fetchall()
                    classsuper = {}
                    for row in rows:
                        classsuper[row['class_id']] = row['super_id']
                    deepresults = set(results)
                    for result in results:
                        super_id = classsuper[result]
                        while super_id is not None:
                            if super_id in results:
                                deepresults.discard(result)
                            super_id = classsuper[super_id]

                    if len(deepresults) == 1:
                        query = """
                            UPDATE {mtype}
                            SET topid=:topid
                            WHERE id=:id
                        """.format(mtype=mtype)
                        cur.execute(query, {'topid': list(deepresults)[0], 'id': member_id})
                    else:
                        query = """
                            SELECT m.notch AS notch , m.searge AS searge, m.name AS name
                            FROM {mtype} m
                            WHERE id={member_id}
                        """.format(mtype=mtype, member_id=member_id)
                        cur.execute(query)
                        rows = cur.fetchall()

                        _nname = rows[0]['notch']
                        _sname = rows[0]['searge']
                        _hname = rows[0]['name']

                        if (_nname == 'this$0'):
                            candidate = cnames[0].split('$')[0]

                            query = """
                                SELECT id AS class_id
                                FROM classes
                                WHERE name=:name
                                  AND side=:side AND versionid=:versionid
                            """
                            cur.execute(query, {'name': candidate, 'side': SIDE_LOOKUP[side], 'versionid': version_id})
                            rows = cur.fetchall()

                            query = """
                                UPDATE {mtype}
                                SET topid=:topid
                                WHERE id=:id
                            """.format(mtype=mtype)
                            cur.execute(query, {'topid': rows[0]['class_id'], 'id': member_id})


                        else:
                            errors.append("%d : \nMember : %s %s %s\nCandidates : %s" % (member_id, _nname, _sname, _hname, cnames))

                        #raise Exception("WE COULDN'T FIND A TOP ID FOR %d : \nMember : %s %s %s\nCandidates : %s" % (member_id, _nname, _sname, _hname, cnames))

            if errors:
                print "Couldn't find TopID of those methods"
                for error in errors:
                    print error
                raise Exception("Everything is going to shit")



def update_sigs(db, side, version_id):
    sigs = {}
    with closing(db.cursor()) as cur:
        query = """
            SELECT name, notch
            FROM classes
            WHERE side=:side AND versionid=:versionid
        """
        cur.execute(query, {'side': SIDE_LOOKUP[side], 'versionid': version_id})
        classes_results = cur.fetchall()
        query = """
            SELECT id AS method_id, sig
            FROM methods
            WHERE sig IS NOT NULL AND notchsig IS NULL
              AND side=:side AND versionid=:versionid
        """
        cur.execute(query, {'side': SIDE_LOOKUP[side], 'versionid': version_id})
        methods_results = cur.fetchall()
        query = """
            SELECT id AS field_id, sig
            FROM fields
            WHERE sig IS NOT NULL AND notchsig IS NULL
              AND side=:side AND versionid=:versionid
        """
        cur.execute(query, {'side': SIDE_LOOKUP[side], 'versionid': version_id})
        fields_results = cur.fetchall()

        for method_res in methods_results:
            if method_res['sig'] not in sigs:
                notchsig = method_res['sig']
                for class_res in classes_results:
                    notchsig = notchsig.replace('L%s;' % class_res['name'], 'L%s;' % class_res['notch'])
                sigs[method_res['sig']] = notchsig
            else:
                notchsig = sigs[method_res['sig']]
            query = """
                UPDATE methods
                SET notchsig=:notchsig
                WHERE id=:id
            """
            cur.execute(query, {'notchsig': notchsig, 'id': method_res['method_id']})

        for field_res in fields_results:
            if field_res['sig'] not in sigs:
                notchsig = field_res['sig']
                for class_res in classes_results:
                    notchsig = notchsig.replace('L%s;' % class_res['name'], 'L%s;' % class_res['notch'])
                sigs[field_res['sig']] = notchsig
            else:
                notchsig = sigs[field_res['sig']]
            query = """
                UPDATE fields
                SET notchsig=:notchsig
                WHERE id=:id
            """
            cur.execute(query, {'notchsig': notchsig, 'id': field_res['field_id']})


def import_csv(db, version_id, datapath):
    with closing(db.cursor()) as cur:
        with open(os.path.join(datapath, 'methods.csv'), 'rb') as fh:
            method_csv = csv.DictReader(fh)
            for method in method_csv:
                description = method['desc']
                if description == '':
                    description = None
                query = """
                    UPDATE methods
                    SET name=:name, desc=:desc
                    WHERE searge=:searge
                      AND side=:side AND versionid=:versionid
                """
                cur.execute(query, {'name': method['name'], 'desc': description, 'searge': method['searge'],
                                    'side': method['side'], 'versionid': version_id})

        with open(os.path.join(datapath, 'fields.csv'), 'rb') as fh:
            field_csv = csv.DictReader(fh)
            for field in field_csv:
                description = field['desc']
                if description == '':
                    description = None
                query = """
                    UPDATE fields
                    SET name=:name, desc=:desc
                    WHERE searge=:searge
                      AND side=:side AND versionid=:versionid
                """
                cur.execute(query, {'name': field['name'], 'desc': description, 'searge': field['searge'],
                                    'side': field['side'], 'versionid': version_id})

        # fill deobf names for all unset members
        query = """
            UPDATE methods
            SET name=searge
            WHERE name IS NULL
              AND versionid=:versionid
        """
        cur.execute(query, {'versionid': version_id})
        query = """
            UPDATE fields
            SET name=searge
            WHERE name IS NULL
              AND versionid=:versionid
        """
        cur.execute(query, {'versionid': version_id})


def db_update(db_name, mcpversion, clientversion, serverversion):
    totaltime = time.time()

    datapath = os.path.join('data', mcpversion)

    os.stat(datapath)
    os.stat(os.path.join(datapath, 'client.srg'))
    os.stat(os.path.join(datapath, 'server.srg'))
    os.stat(os.path.join(datapath, 'methods.csv'))
    os.stat(os.path.join(datapath, 'fields.csv'))
    os.stat(os.path.join(datapath, 'client_recomp.jar'))
    os.stat(os.path.join(datapath, 'server_recomp.jar'))

    with get_db(db_name) as db:
        with closing(db.cursor()) as cur:
            # We insert the new version informations and get the id back
            query = """
                INSERT INTO versions (mcpversion, botversion, dbversion, clientversion, serverversion, timestamp)
                VALUES (:mcpversion, :botversion, :dbversion, :clientversion, :serverversion, :timestamp)
            """
            cur.execute(query, {'mcpversion': mcpversion, 'botversion': '1.0', 'dbversion': '1.0',
                                'clientversion': clientversion, 'serverversion': serverversion,
                                'timestamp': int(time.time())})
            version_id = cur.lastrowid

            query = """
                UPDATE config
                SET value=:value
                WHERE name=:name
            """
            cur.execute(query, {'name': 'currentversion', 'value': version_id})

        for side in ['server', 'client']:
            print '> Reading data from %s class files' % side
            classtime = time.time()
            import_jar(db, side, version_id, datapath)
            print '> Class data for %s read in %.2f seconds' % (side, time.time() - classtime)

            print '> Reading data from %s SRG file' % side
            srgtime = time.time()
            import_srg(db, side, version_id, datapath)
            print '> SRG data for %s read in %.2f seconds' % (side, time.time() - srgtime)

            print '> Updating misc data for %s' % side
            misctime = time.time()
            update_misc(db, side, version_id)
            print '> Misc data for %s updated in %.2f seconds' % (side, time.time() - misctime)

            print '> Updating notch signatures for %s' % side
            sigtime = time.time()
            update_sigs(db, side, version_id)
            print '> Signatures for %s updated in %.2f seconds' % (side, time.time() - sigtime)

        print '> Reading data from CSV files'
        csvtime = time.time()
        import_csv(db, version_id, datapath)
        print '> CSV data read in %.2f seconds' % (time.time() - csvtime)

    print '> Done in %.2f seconds' % (time.time() - totaltime)


def main():
    parser = argparse.ArgumentParser(description='Import MCP data')
    parser.add_argument('mcp_version')
    parser.add_argument('client_version')
    parser.add_argument('server_version')
    parser.add_argument('-d', '--database', help='database file', default='database.sqlite')
    args = parser.parse_args()
    db_update(args.database, args.mcp_version, args.client_version, args.server_version)


if __name__ == '__main__':
    main()
