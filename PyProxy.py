#!/usr/bin/env python
#=========================================================#
# [+] Title: Simple Asynchronous HTTP Proxy               #
# [+] Script: pyproxy.py                                  #
# [+] Website: http://www.pythonforpentesting.com         #
# [+] Twitter: @OffensivePython                           #
#=========================================================#

import socket
import select
import sys
import re

server = socket.socket()
internal = [] # Internal connections (browser)
pipe = {}     # dst_socket:src_socket

# CONSTANTS
MAXSIZE = 65535
# Unresolved/HTTPS domain
error_header = (
    b"HTTP/1.1 404 Not Found\r\n"
    b"Connection: Close\r\n\r\n"
    )
# Usage
usage = (
    "usage: pyproxy.py port\r\n"
    "Port should be in range 0-65535\r\n"
    "e.g: pyproxy.py 8080"
    )

def recvall(sock):
    data = b""
    while True:
        r, w, e = select.select([sock], [], [], 0.5)
        if r:
            chunk = sock.recv(MAXSIZE)
            if chunk:
                data+= chunk
            else:
                break
        else:
            break
    return data

def accept_connection(sock):
    connection, address = sock.accept()
    internal.append(connection)

def get_request_info(request):
    method = re.match(b"([A-Z]+?) ", request)
    if method:
        req = re.match(b"(.*?)\r\n", request).group(1).decode()
        method = method.group(1).decode()
        if method=="CONNECT":
            address = re.search(b"CONNECT (.*?):(.*?) HTTP", request)
            host, port = address.group(1).decode(), int(address.group(2).decode())
        else:
            host = re.search(b"Host: (.*?)\r\n", request).group(1).decode()
            port = 80
        try:
            host = socket.gethostbyname(host)
        except socket.gaierror:
            host = "UNRESOLVED"
    else:
        method = None
        host = None
        port = None
    return method, host, port, req


def connecto(host, port):
    sock = socket.socket()
    try:
        sock.connect((host, port))
    except socket.error:
        sock.close()
        sock = None
    return sock

def forward_requests(socklist):
    r, w, e = select.select(socklist, [], socklist)
    for src in r:
        if src==server:
            accept_connection(src)
        else:
            request = recvall(src)
            if request:
                method, host, port, req = get_request_info(request)
                if host=="UNRESOLVED" or method=="CONNECT":
                    src.send(error_header)
                    internal.remove(src)
                    src.close()
                elif host:
                    print("[+]", req)
                    dst = connecto(host, port)
                    dst.send(request)
                    pipe[dst] = src
            else:
                internal.remove(src)
                for dst in pipe:
                    if pipe[dst]==src:
                        del pipe[dst]
                        dst.close()
                        break
                src.close()
    
def forward_responses(socklist):
    if socklist:
        r, w, e = select.select(socklist, [], [], 1)
        for dst in r:
            src = pipe[dst]
            response = recvall(dst)
            if response:
                src.send(response)
            internal.remove(src)
            del pipe[dst]
            src.close()
            dst.close()

def cleanup():
    for c in internal:
       c.close()
    for p in pipe:
        p.close()

def main():
    args = sys.argv
    if len(args)==2: 
        try:
            port = int(args[1])
            if port>MAXSIZE:
                raise ValueError("Port should be in range(65535)")
        except ValueError as err:
                print(err)
                sys.exit()
    else:
        print(usage)
        sys.exit()
    print("[+] PyProxy Listening on port %d"%port)
    server.bind(("127.0.0.1", port))
    server.listen(5)
    internal.append(server)
    try:
        while True:
            forward_requests(internal)
            forward_responses(list(pipe.keys()))
    except KeyboardInterrupt:
        print("[+] Exiting")
        cleanup()
        sys.exit()
        
if __name__=="__main__":
    main()
