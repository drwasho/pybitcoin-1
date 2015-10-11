__author__ = 'chris'
import sqlite3 as lite
from bitcoin.core import CBlockHeader, CheckBlockHeader, CheckBlockHeaderError, b2lx, lx
from bitcoin.net import CBlockLocator

TESTNET_CHECKPOINT = (0, 577254, "0000000000000f313c366eb2f8f12623d977a08c281e574bdc1a93eda15349e8", "", 0)


class BlockDatabase(object):

    def __init__(self, filepath, testnet=False):
        self.db = lite.connect(filepath)
        self.db.text_factory = str
        try:
            self._create_tables(testnet)
        except Exception:
            pass

    def _create_tables(self, testnet):
        cursor = self.db.cursor()
        cursor.execute('''CREATE TABLE blocks(totalWork INTEGER PRIMARY KEY, height INTEGER, blockID TEXT, hashOfPrevious TEXT, timestamp INTEGER)''')

        cursor.execute('''CREATE INDEX blockIndx ON blocks(blockID);''')

        cursor.execute('''INSERT INTO blocks(totalWork, height, blockID, hashOfPrevious, timestamp) VALUES (?,?,?,?,?)''',
                       (TESTNET_CHECKPOINT[0], TESTNET_CHECKPOINT[1], TESTNET_CHECKPOINT[2], TESTNET_CHECKPOINT[3], TESTNET_CHECKPOINT[4]))

        self.db.commit()

    def _commit_block(self, height, block_id, hash_of_previous, bits, timestamp):
        cursor = self.db.cursor()
        cursor.execute('''SELECT totalWork FROM blocks WHERE height=?''', (height-1,))
        total_work = cursor.fetchone()[0]
        cursor = self.db.cursor()
        cursor.execute('''INSERT INTO blocks(totalWork, height, blockID, hashOfPrevious, timestamp) VALUES (?,?,?,?,?)''',
                       (total_work + bits, height, block_id, hash_of_previous, timestamp))
        self.db.commit()
        self._cull()

    def _get_parent_height(self, header):
        cursor = self.db.cursor()
        cursor.execute('''SELECT height FROM blocks WHERE blockID=?''', (b2lx(header.hashPrevBlock),))
        height = cursor.fetchone()[0]
        if height is not None:
            return height
        else:
            return None

    def _get_starting_height(self):
        cursor = self.db.cursor()
        cursor.execute('''SELECT height FROM blocks ORDER BY ROWID ASC LIMIT 1''')
        return cursor.fetchone()[0]

    def _cull(self):
        cursor = self.db.cursor()
        start = self._get_starting_height()
        end = self.get_height()
        if end - start > 5000:
            for i in range(end-start):
                cursor.execute('''DELETE FROM blocks WHERE height=?''', (start+i,))

    def get_block_id(self, height):
        cursor = self.db.cursor()
        cursor.execute('''SELECT blockID FROM blocks WHERE height = ?;''', (height,))
        return cursor.fetchone()[0]

    def get_height(self):
        cursor = self.db.cursor()
        cursor.execute('''SELECT height FROM blocks WHERE totalWork = (SELECT MAX(totalWork) FROM blocks);''')
        return cursor.fetchone()[0]

    def get_locator(self):
        """
        Given the db setup, this function may return orphans. This isn't the end of the world, however, as
        it just means the remote peer will send more blocks than we need.
        """
        # TODO: add some logic to avoid returning orphans

        locator = CBlockLocator()

        step = -1
        start = 0
        for i in range(self.get_height(), self._get_starting_height()-1, step):
            if start >= 10:
                step *= 2
                start = 0
            locator.vHave.append(lx(self.get_block_id(i)))
            start += 1
        return locator

    def process_block(self, block):
        try:
            header = block if isinstance(block, CBlockHeader) else block.get_header()
            CheckBlockHeader(header, True)
            # TODO: reject if timestamp is median of last 11 blocks
            # TODO: check that nBits value matches the difficulty rules
            h = self._get_parent_height(header)
            if h is not None:
                self._commit_block(h + 1, b2lx(header.GetHash()), b2lx(header.hashPrevBlock), header.nBits, header.nTime)

        except CheckBlockHeaderError:
            pass
