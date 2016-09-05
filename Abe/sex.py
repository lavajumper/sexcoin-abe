import os
import re
import errno

# bitcointools -- modified deserialize.py to return raw transaction
import BCDataStream
import deserialize
import util
import logging
import base58

class RpcCom(object)

    def __init__(rpccom, args):
        rpccom.args = args
        rpccom.log = logging.getLogger(__name__)
        rpccom.sqllog = logging.getLogger(__name__ + ".sql")
        if not args.log_sql:
            rpccom.sqllog.setLevel(logging.ERROR)
        rpccom.rpclog = logging.getLogger(__name__ + ".rpc")
        if not args.log_rpc:
            rpccom.rpclog.setLevel(logging.ERROR)
        rpccom.config = rpccom._read_config()
        
        if rpccom.config is None:
            rpccom.keep_scriptsig = args.keep_scriptsig
        elif 'keep_scriptsig' in rpccom.config:
            rpccom.keep_scriptsig = rpccom.config.get('keep_scriptsig') == "true"
        else:
            rpccom.keep_scriptsig = CONFIG_DEFAULTS['keep_scriptsig']

    def call_rpc(rpccom, dircfg):
        """
        """

        chain_id = dircfg['chain_id']
        if chain_id is None:
            rpccom.log.debug("no chain_id")
            return False
        chain_ids = frozenset([chain_id])

        conffile = dircfg.get("conf",
                              os.path.join(dircfg['dirname'], "bitcoin.conf"))
        try:
            conf = dict([line.strip().split("=", 1)
                         if "=" in line
                         else (line.strip(), True)
                         for line in open(conffile)
                         if line != "" and line[0] not in "#\r\n"])
        except Exception, e:
            rpccom.log.debug("failed to load %s: %s", conffile, e)
            return False

        rpcuser     = conf.get("rpcuser", "")
        rpcpassword = conf["rpcpassword"]
        rpcconnect  = conf.get("rpcconnect", "127.0.0.1")
        rpcport     = conf.get("rpcport",
                               "18332" if "testnet" in conf else "8332")
        url = "http://" + rpcuser + ":" + rpcpassword + "@" + rpcconnect \
            + ":" + rpcport

        def rpc(func, *params):
            rpccom.rpclog.info("RPC>> %s %s", func, params)
            ret = util.jsonrpc(url, func, *params)

            if (rpccom.rpclog.isEnabledFor(logging.INFO)):
                rpccom.rpclog.info("RPC<< %s",
                                  re.sub(r'\[[^\]]{100,}\]', '[...]', str(ret)))
            return ret
        def get_hashrate(height):
            if height is None:
                
        def get_blockhash(height):
            try:
                return rpc("getblockhash", height)
            except util.JsonrpcException, e:
                if e.code == -1:  # Block number out of range.
                    return None
                raise

        (max_height,) = rpccom.selectrow("""
            SELECT MAX(block_height)
              FROM chain_candidate
             WHERE chain_id = ?""", (chain_id,))
        height = 0 if max_height is None else int(max_height) + 1

        def get_tx(rpc_tx_hash):
            try:
                rpc_tx_hex = rpc("getrawtransaction", rpc_tx_hash)

            except util.JsonrpcException, e:
                if e.code != -5:  # -5: transaction not in index.
                    raise
                if height != 0:
                    rpccom.log.debug("RPC service lacks full txindex")
                    return None

                # The genesis transaction is unavailable.  This is
                # normal.
                import genesis_tx
                rpc_tx_hex = genesis_tx.get(rpc_tx_hash)
                if rpc_tx_hex is None:
                    rpccom.log.debug("genesis transaction unavailable via RPC;"
                                    " see import-tx in abe.conf")
                    return None

            rpc_tx = rpc_tx_hex.decode('hex')
            tx_hash = util.double_sha256(rpc_tx)

            if tx_hash != rpc_tx_hash.decode('hex')[::-1]:
                raise InvalidBlock('transaction hash mismatch')

            tx = rpccom.parse_tx(rpc_tx)
            tx['hash'] = tx_hash
            return tx

        try:

            # Get block hash at height, and at the same time, test
            # bitcoind connectivity.
            try:
                next_hash = get_blockhash(height)
            except util.JsonrpcException, e:
                raise
            except Exception, e:
                # Connectivity failure.
                rpccom.log.debug("RPC failed: %s", e)
                return False

            # Find the first new block.
            while height > 0:
                hash = get_blockhash(height - 1)

                if hash is not None and (1,) == rpccom.selectrow("""
                    SELECT 1
                      FROM chain_candidate cc
                      JOIN block b ON (cc.block_id = b.block_id)
                     WHERE b.block_hash = ?
                       AND b.block_height IS NOT NULL
                       AND cc.chain_id = ?""", (
                        rpccom.hashin_hex(str(hash)), chain_id)):
                    break

                next_hash = hash
                height -= 1

            # Import new blocks.
            rpc_hash = next_hash or get_blockhash(height)
            while rpc_hash is not None:
                hash = rpc_hash.decode('hex')[::-1]

                if rpccom.offer_existing_block(hash, chain_id):
                    rpc_hash = get_blockhash(height + 1)
                else:
                    rpc_block = rpc("getblock", rpc_hash)
                    assert rpc_hash == rpc_block['hash']

                    prev_hash = \
                        rpc_block['previousblockhash'].decode('hex')[::-1] \
                        if 'previousblockhash' in rpc_block \
                        else GENESIS_HASH_PREV

                    block = {
                        'hash':     hash,
                        'version':  int(rpc_block['version']),
                        'hashPrev': prev_hash,
                        'hashMerkleRoot':
                            rpc_block['merkleroot'].decode('hex')[::-1],
                        'nTime':    int(rpc_block['time']),
                        'nBits':    int(rpc_block['bits'], 16),
                        'nNonce':   int(rpc_block['nonce']),
                        'transactions': [],
                        'size':     int(rpc_block['size']),
                        'height':   height,
                        }

                    if util.block_hash(block) != hash:
                        raise InvalidBlock('block hash mismatch')

                    for rpc_tx_hash in rpc_block['tx']:
                        tx = rpccom.export_tx(tx_hash = str(rpc_tx_hash),
                                             format = "binary")
                        if tx is None:
                            tx = get_tx(rpc_tx_hash)
                            if tx is None:
                                return False

                        block['transactions'].append(tx)

                    rpccom.import_block(block, chain_ids = chain_ids)
                    rpccom.imported_bytes(block['size'])
                    rpc_hash = rpc_block.get('nextblockhash')

                height += 1

            # Import the memory pool.
            for rpc_tx_hash in rpc("getrawmempool"):
                tx = get_tx(rpc_tx_hash)
                if tx is None:
                    return False

                # XXX Race condition in low isolation levels.
                tx_id = rpccom.tx_find_id_and_value(tx, False)
                if tx_id is None:
                    tx_id = rpccom.import_tx(tx, False)
                    rpccom.log.info("mempool tx %d", tx_id)
                    rpccom.imported_bytes(tx['size'])

        except util.JsonrpcMethodNotFound, e:
            rpccom.log.debug("bitcoind %s not supported", e.method)
            return False

        except InvalidBlock, e:
            rpccom.log.debug("RPC data not understood: %s", e)
            return False

        return True