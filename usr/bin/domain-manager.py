#! /usr/bin/env python2
# coding: utf-8

import traceback
import cgi
import urlparse
import re
import dns.resolver
import dns.query
import dns.update
import dns.reversename
import dns.zone
import dns.exception

HEADER = """<!doctype html>
<meta charset="utf-8" />
<link rel="stylesheet" href="/bootstrap.min.css">
<title>Domain-Manager</title>
<div class="container">
  <h2>Domain-Manager</h2>
  <ul class="nav nav-tabs">
    <li%s>
      <a href="http://ipv4.dns.ballern.net/domains">IPv4</a>
    </li>
    <li%s>
      <a href="http://ipv6.dns.ballern.net/domains">IPv6</a>
    </li>
  </ul>
  <br />
  <div class="panel panel-default">
    <div class="panel-heading">Your domain</div>
    <div class="panel-body">
"""

DOMAIN = "      <h4><span class=\"label label-default\">%s</span></h4>"
NO_DOMAIN = "      <h4><span class=\"label label-danger\">Could not resolve domain.</span></h4>"

HEADER2 = """
    </div>
  </div>
  <div class="panel panel-default">
    <div class="panel-heading">Add a domain</div>
    <div class="panel-body">
      <form class="form-inline">
        <input type="hidden" name="action" value="add" />
        <div class="input-group">
          <input class="form-control" placeholder="domain" name="domain" />
          <span class="input-group-addon">.ballern.net</span>
        </div>
        <button type="submit" class="btn btn-default">Add</button>
      </form>
    </div>
  </div>
  <div class="panel panel-default">
    <div class="panel-heading">Domain overview</div>
      <table class="table">
        <tr><th>Name</th><th>IP</th><th>Delete</th></tr>
"""

ROW = """        <tr><td><a href="http://%s.ballern.net">%s</a></td><td>%s</td><td>%s</td></tr>
"""
ROW_AT = """        <tr><td><a href="http://ballern.net">%s</a></td><td>%s</td><td>%s</td></tr>
"""

DELETE = "<a href=\"?action=delete&amp;domain=%s\" class=\"btn btn-default\">🗑 delete</a>"

FOOTER = """      </table>
    </div>
  </div>
</div>"""

def validate_domain(domain):
    domain = re.sub("-*\.-*", ".", domain.strip("-.").lower())
    return re.sub("[^a-z0-9.-]", "", domain.encode("idna"))

def switch_ip(ip):	
    if ip[:7] == "::ffff:":
        return 'a', ip[7:]
    else:
        return 'aaaa', ip

def app(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/html')])

    yield '<h1>FastCGI Environment</h1>'
    yield '<table>'
    for k, v in sorted(environ.items()):
         yield '<tr><th>%s</th><td>%s</td></tr>' % (cgi.escape(k), cgi.escape(v))
    yield '</table>'

def info_page(env, responde, record, ip):
    responde('200 Here you go', [('Content-Type', 'text/html')])
    if record == "a":
        yield HEADER % (" class=\"active\"", "")
    else:
        yield HEADER % ("", " class=\"active\"")
    try:
        addr = dns.reversename.from_address(ip)
        yield DOMAIN % str(dns.resolver.query(addr, "PTR")[0])
    except dns.exception.DNSException:
        traceback.print_exc()
        yield NO_DOMAIN
    yield HEADER2
    try:
        zone = dns.zone.from_xfr(dns.query.xfr("127.0.0.1", "ballern.net"))
        domains = zone.nodes.keys()
        domains.sort()
        for domain in domains:
            a_record = zone.get_rdataset(domain, record)
            if a_record:
                addr = str(a_record.items[0])
                name = str(domain).decode("idna").encode("utf-8")
                if addr == ip:
                    delete = DELETE % name
                else:
                    delete = ""
                if str(domain) == "@":
                    yield ROW_AT % (name, addr, delete)
                else:
                    yield ROW % (str(domain), name, addr, delete)
    except dns.exception.DNSException:
        traceback.print_exc()
        yield ROW % ("Error", "loading", "domains")
    yield FOOTER 

def domain_add(domain, record, ip):
    try:
        dns.resolver.query(domain + ".ballern.net", record)
    except dns.resolver.NXDOMAIN:
        update = dns.update.Update("ballern.net")
        update.replace(domain, 300, record, ip)
        dns.query.tcp(update, "127.0.0.1")
    except dns.resolver.NoAnswer:
        update = dns.update.Update("ballern.net")
        update.replace(domain, 300, record, ip)
        dns.query.tcp(update, "127.0.0.1")

def domain_delete(domain, record, ip):
    answer = dns.resolver.query(domain + ".ballern.net", record)
    for record in answer:
        if record.address == ip:
            break
    else:
        return
    update = dns.update.Update("ballern.net")
    update.delete(domain, record)
    dns.query.tcp(update, "127.0.0.1")
        

def domain_manager(env, responde):
    record, ip = switch_ip(env["REMOTE_ADDR"])
    if not env["QUERY_STRING"]:
        return info_page(env, responde, record, ip)
    params = urlparse.parse_qs(env["QUERY_STRING"])
    if "action" in params and "domain" in params:
        domain = validate_domain(params["domain"][0].decode("utf-8"))
        if domain:
            if "add" in params["action"]:
                 domain_add(domain, record, ip)
            elif "delete" in params["action"]:
                 domain_delete(domain, record, ip)
    responde("303 Did it. Now go back", [("Location", env.get("HTTP_REFERER", env["SCRIPT_NAME"]))])
    return []


if __name__ == "__main__":
    from flup.server.fcgi import WSGIServer
    WSGIServer(domain_manager).run()
