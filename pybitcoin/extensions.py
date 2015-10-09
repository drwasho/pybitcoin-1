__author__ = 'chris'
import random
import struct
import bitcoin
import math
from bitcoin.messages import msg_version, MsgSerializable
from bitcoin.core.serialize import VarStringSerializer
from bitcoin.bloom import CBloomFilter


PROTO_VERSION = 70002


class msg_version2(msg_version):
    """
    An extension of the python-bitcoinlib message class which bumps
    the version number and adds the relay boolean. Also changes the
    default services to zero.
    """

    def __init__(self, protover=PROTO_VERSION, user_agent="/pyBitcoin0.1/"):
        super(msg_version2, self).__init__(protover)
        self.relay = False
        self.nServices = 0
        self.strSubVer = user_agent
        self.addrFrom.nServices = 0

    def msg_ser(self, f):
        f.write(struct.pack(b"<i", self.nVersion))
        f.write(struct.pack(b"<Q", self.nServices))
        f.write(struct.pack(b"<q", self.nTime))
        self.addrTo.stream_serialize(f, True)
        self.addrFrom.stream_serialize(f, True)
        f.write(struct.pack(b"<Q", self.nNonce))
        VarStringSerializer.stream_serialize(self.strSubVer, f)
        f.write(struct.pack(b"<i", self.nStartingHeight))
        f.write(struct.pack('?', self.relay))


class msg_filterload(MsgSerializable):
    """
    A filter load message that is missing from python-bitcoinlib
    """
    command = b"filterload"

    def __init__(self, protover=PROTO_VERSION, filter=None):
        super(msg_filterload, self).__init__(protover)
        self.protover = protover
        if not filter:
            self.filter = BloomFilter(3, 0.01, random.getrandbits(32), CBloomFilter.UPDATE_NONE)
        else:
            self.filter = filter

    @classmethod
    def msg_deser(cls, f, protover=PROTO_VERSION):
        c = cls()
        c.filter = CBloomFilter.stream_deserialize(f)
        return c

    def msg_ser(self, f):
        self.filter.stream_serialize(f)

    def __repr__(self):
        return "msg_filterload(vData=%i nHashFunctions=%i nTweak=%i nFlags=%i" % (self.filter.vData, self.filter.nHashFunctions, self.filter.nTweak, self.filter.nFlags)


class BloomFilter(CBloomFilter):
    """
    An extension of the python-bitcoinlib CBloomFilter class to allow for
    removal of inserted objects.
    """

    def __init__(self, nElements, nFPRate, nTweak, nFlags):
        super(BloomFilter, self).__init__(nElements, nFPRate, nTweak, nFlags)
        self._elements = []
        self.nFPRate = nFPRate
        self.nElements = nElements

    __bit_mask = bytearray([0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80])
    def insert(self, elem):
        """Insert an element in the filter.
        elem may be a COutPoint or bytes
        """
        if isinstance(elem, bitcoin.core.COutPoint):
            elem = elem.serialize()

        if len(self.vData) == 1 and self.vData[0] == 0xff:
            return

        for i in range(0, self.nHashFuncs):
            nIndex = self.bloom_hash(i, elem)
            # Sets bit nIndex of vData
            self.vData[nIndex >> 3] |= self.__bit_mask[7 & nIndex]

        self._elements.append(elem)

    def remove(self, elem):
        """
        Remove an element from the bloom filter. Works by clearing the filter and re-inserting
        the elements that weren't removed.
        """
        LN2SQUARED = 0.4804530139182014246671025263266649717305529515945455
        LN2 = 0.6931471805599453094172321214581765680755001343602552
        if elem in self._elements:
            self._elements.remove(elem)
            self.vData = bytearray(int(min(-1  / LN2SQUARED * self.nElements * math.log(self.nFPRate), self.MAX_BLOOM_FILTER_SIZE * 8) / 8))
            self.nHashFuncs = int(min(len(self.vData) * 8 / self.nElements * LN2, self.MAX_HASH_FUNCS))

            for element in self._elements:
                self.insert(element)