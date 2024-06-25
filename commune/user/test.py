
import commune as c
from typing import Dict , Any, List
import json
import os


class UserTest(c.Module):
    ##################################
    # USER LAND
    ##################################

    def test_blacklisting(self):
        blacklist = self.blacklist()
        key = c.get_key('test')
        assert key.ss58_address not in self.blacklist(), 'key already blacklisted'
        self.blacklist_user(key.ss58_address)
        assert key.ss58_address in self.blacklist(), 'key not blacklisted'
        self.whitelist_user(key.ss58_address)
        assert key.ss58_address not in self.blacklist(), 'key not whitelisted'
        return {'success': True, 'msg': 'blacklist test passed'}
        

