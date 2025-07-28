import asyncio
from app.db.pg_utils import get_file_owners
from app.db.db_utils import add_file_acl
from app.db.models import PermissionEnum

async def sync_pg_file_owners_to_mysql_acl():
    records = get_file_owners()
    print(f"Found {len(records)} files to sync.")
    for uid, owner_id, name in records:  # Make sure get_file_owners() returns name too
        print(f"Syncing file {uid} owner {owner_id}, filename={name}...")
        await add_file_acl(file_id=uid, user_id=owner_id, access_type=PermissionEnum.owner, filename=name)
    print("All ACLs synced successfully.")

def sync_acl_main():
    print("Starting ACL sync...") 
    asyncio.run(sync_pg_file_owners_to_mysql_acl())  
    print("Finished ACL sync.")

if __name__ == "__main__":
    sync_acl_main()
