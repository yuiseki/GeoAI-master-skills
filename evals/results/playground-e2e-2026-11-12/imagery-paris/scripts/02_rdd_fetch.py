import sys
from remotezip import RemoteZip
url="https://ndownloader.figshare.com/files/38030910"
with RemoteZip(url) as z:
    names=z.namelist()
    print(len(names)); 
    for n in names[:15]: print(n, z.getinfo(n).file_size)
    for n in names:
        if n.endswith("Czech.zip") or n.endswith("United_States.zip"):
            print("extract",n)
            z.extract(n,"rdd")
