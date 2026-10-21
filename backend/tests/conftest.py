import os, tempfile
os.environ["SHOP_DB_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"   # tests never touch the real database
