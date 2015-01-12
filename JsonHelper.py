import urllib2, json

def get_remote_json(url):
    """Attempts to retrieve a json document from the given URL.

    :type url: str
    :rtype: dict
    """
    req = urllib2.Request(url)
    r = urllib2.urlopen(req)
    ret = json.loads(r.read())
    return ret


def get_json_value(json_obj, key):
    """Gets the value of the given Json key.
    Key should be in the form <parent>[/<child>]* if not in the root of the tree.

    :type json_obj: dict
    :type key: str
    :rtype: dict | list | str | int | long | float | True | False | None
    """
    value = json_obj
    splitted = key.split('/')
    for subkey in splitted:
        value = value[subkey]
    return value
