#!/usr/bin/env python3
"""copyparty event hook: tell Bifrost that files changed"""

import sys
import urllib.request

url, token = sys.argv[1], sys.argv[2]
request = urllib.request.Request(url, data=b"", method="POST", headers={"X-Bifrost-Token": token})
urllib.request.urlopen(request, timeout=10).read()
