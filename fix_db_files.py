import asyncio
from sqlalchemy import select, update
from app.db.session import AsyncSessionLocal
from app.db.models import File

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(File).where(File.project_id == '793e6684-b06b-48e3-84ce-1b627dca4327'))
        files = result.scalars().all()
        count = 0
        for f in files:
            if r"\n" in f.content and "\n" not in f.content:
                new_content = f.content.replace(r"\n", "\n").replace(r"\'", "'").replace(r'\"', '"')
                f.content = new_content
                count += 1
        await db.commit()
        print(f"Fixed {count} files!")

asyncio.run(main())
