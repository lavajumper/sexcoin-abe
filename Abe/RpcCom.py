import os
import re
import errno

# bitcointools -- modified deserialize.py to return raw transaction
import BCDataStream
import deserialize
import util
import logging
import base58

class RpcCom(object):

    def __init__(rpccom, args):
        rpccom.args = args
        rpccom.log = logging.getLogger(__name__)

    def request(rpccom, command):
        conffile = "/home/sexcoin/sexcoin.conf"
        try:
            conf = dict([line.strip().split("=", 1)
                         if "=" in line
                         else (line.strip(), True)
                         for line in open(conffile)
                         if line != "" and line[0] not in "#\r\n"])
        except Exception, e:
            rpccom.log.info("failed to load %s: %s", conffile, e)
            return False

        rpcuser     = conf.get("rpcuser", "")
        rpcpassword = conf["rpcpassword"]
        rpcconnect  = "127.0.0.1"  #conf.get("rpcconnect", "127.0.0.1")
        rpcport = conf.get("rpcport", "195361" if "testnet" in conf else "9561")
        
                               
        url = "http://" + rpcuser + ":" + rpcpassword + "@" + rpcconnect \
            + ":" + rpcport
        
        rpccom.log.info("RPC>> %s", command)
        ret = util.jsonrpc(url, command )
        rpccom.log.info("RPC<< %s",
            re.sub(r'\[[^\]]{100,}\]', '[...]', str(ret)))
        return ret

def new(args):
    return RpcCom(args)
    