from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import str
from builtins import object
from beem.instance import shared_steem_instance
import random
from beembase import memo as BtsMemo
from beembase.account import PrivateKey, PublicKey
from .account import Account
from .exceptions import MissingKeyError, KeyNotFound


class Memo(object):
    """ Deals with Memos that are attached to a transfer

        :param beem.account.Account from_account: Account that has sent the memo
        :param beem.account.Account to_account: Account that has received the memo
        :param beem.steem.Steem steem_instance: Steem instance

        A memo is encrypted with a shared secret derived from a private key of
        the sender and a public key of the receiver. Due to the underlying
        mathematics, the same shared secret can be derived by the private key
        of the receiver and the public key of the sender. The encrypted message
        is perturbed by a nonce that is part of the transmitted message.

        .. code-block:: python

            from beem.memo import Memo
            m = Memo("steemeu", "wallet.xeroc")
            m.steem.wallet.unlock("secret")
            enc = (m.encrypt("foobar"))
            print(enc)
            >> {'nonce': '17329630356955254641', 'message': '8563e2bb2976e0217806d642901a2855'}
            print(m.decrypt(enc))
            >> foobar

        To decrypt a memo, simply use

        .. code-block:: python

            from beem.memo import Memo
            m = Memo()
            m.steem.wallet.unlock("secret")
            print(memo.decrypt(op_data["memo"]))

        if ``op_data`` being the payload of a transfer operation.

        Memo Keys
        #########

        In BitShares, memos are AES-256 encrypted with a shared secret between sender and
        receiver. It is derived from the memo private key of the sender and the memo
        publick key of the receiver.

        In order for the receiver to decode the memo, the shared secret has to be
        derived from the receiver's private key and the senders public key.

        The memo public key is part of the account and can be retreived with the
        `get_account` call:

        .. code-block:: js

            get_account <accountname>
            {
              [...]
              "options": {
                "memo_key": "GPH5TPTziKkLexhVKsQKtSpo4bAv5RnB8oXcG4sMHEwCcTf3r7dqE",
                [...]
              },
              [...]
            }

        while the memo private key can be dumped with `dump_private_keys`

        Memo Message
        ############

        The take the following form:

        .. code-block:: js

                {
                  "from": "GPH5mgup8evDqMnT86L7scVebRYDC2fwAWmygPEUL43LjstQegYCC",
                  "to": "GPH5Ar4j53kFWuEZQ9XhxbAja4YXMPJ2EnUg5QcrdeMFYUNMMNJbe",
                  "nonce": "13043867485137706821",
                  "message": "d55524c37320920844ca83bb20c8d008"
                }

        The fields `from` and `to` contain the memo public key of sender and receiver.
        The `nonce` is a random integer that is used for the seed of the AES encryption
        of the message.

        Example
        #######

        Encrypting a memo
        ~~~~~~~~~~~~~~~~~

        The high level memo class makes use of the pysteem wallet to obtain keys
        for the corresponding accounts.

        .. code-block:: python

            from beem.memo import Memo
            from beem.account import Account

            memoObj = Memo(
                from_account=Account(from_account),
                to_account=Account(to_account)
            )
            encrypted_memo = memoObj.encrypt(memo)

        Decoding of a received memo
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~

        .. code-block:: python

             from getpass import getpass
             from beem.block import Block
             from beem.memo import Memo

             # Obtain a transfer from the blockchain
             block = Block(23755086)                   # block
             transaction = block["transactions"][3]    # transactions
             op = transaction["operations"][0]         # operation
             op_id = op[0]                             # operation type
             op_data = op[1]                           # operation payload

             # Instantiate Memo for decoding
             memo = Memo()

             # Unlock wallet
             memo.unlock_wallet(getpass())

             # Decode memo
             # Raises exception if required keys not available in the wallet
             print(memo.decrypt(op_data["memo"]))

    """
    def __init__(
        self,
        from_account=None,
        to_account=None,
        steem_instance=None
    ):

        self.steem = steem_instance or shared_steem_instance()

        if to_account:
            self.to_account = Account(to_account, steem_instance=self.steem)
        if from_account:
            self.from_account = Account(from_account, steem_instance=self.steem)

    def unlock_wallet(self, *args, **kwargs):
        """ Unlock the library internal wallet
        """
        self.steem.wallet.unlock(*args, **kwargs)
        return self

    def encrypt(self, memo):
        """ Encrypt a memo

            :param str memo: clear text memo message
            :returns: encrypted memo
            :rtype: str
        """
        if not memo:
            return None

        nonce = str(random.getrandbits(64))
        memo_wif = self.steem.wallet.getPrivateKeyForPublicKey(
            self.from_account["memo_key"]
        )
        if not memo_wif:
            raise MissingKeyError("Memo key for %s missing!" % self.from_account["name"])

        enc = BtsMemo.encode_memo(
            PrivateKey(memo_wif),
            PublicKey(
                self.to_account["memo_key"],
                prefix=self.steem.prefix
            ),
            nonce,
            memo
        )

        return {
            "message": enc,
            "nonce": nonce,
            "from": self.from_account["memo_key"],
            "to": self.to_account["memo_key"]
        }

    def decrypt(self, memo):
        """ Decrypt a memo

            :param str memo: encrypted memo message
            :returns: encrypted memo
            :rtype: str
        """
        if not memo:
            return None

        # We first try to decode assuming we received the memo
        try:
            memo_wif = self.steem.wallet.getPrivateKeyForPublicKey(
                memo["to"]
            )
            pubkey = memo["from"]
        except KeyNotFound:
            try:
                # if that failed, we assume that we have sent the memo
                memo_wif = self.steem.wallet.getPrivateKeyForPublicKey(
                    memo["from"]
                )
                pubkey = memo["to"]
            except KeyNotFound:
                # if all fails, raise exception
                raise MissingKeyError(
                    "Non of the required memo keys are installed!"
                    "Need any of {}".format(
                    [memo["to"], memo["from"]]))

        return BtsMemo.decode_memo(
            PrivateKey(memo_wif),
            PublicKey(pubkey, prefix=self.steem.prefix),
            memo.get("nonce"),
            memo.get("message")
        )