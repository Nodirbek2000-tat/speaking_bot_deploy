
import os
BASE = "E:/Speaking_Bot/speaking_bot"

def wf(relpath, content):
    full = os.path.join(BASE, relpath.replace("/", os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    print("OK:", relpath)

import textwrap

crud = textwrap.dedent("""
    import json
    import uuid
    from datetime import datetime, timedelta
    from sqlalchemy import select, desc

    from .database import async_session
    from .models import User, MockSession, IELTSQuestion, CEFRQuestion, WordBank, SavedWord, DailyActivity


    async def get_or_create_user(telegram_id: int, full_name: str, username: str = None, ref_code: str = None) -> User:
        async with async_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if not user:
                referral_code = str(uuid.uuid4())[:8].upper()
                user = User(telegram_id=telegram_id, full_name=full_name, username=username, referral_code=referral_code)
                if ref_code:
                    ref_result = await session.execute(select(User).where(User.referral_code == ref_code))
                    referrer = ref_result.scalar_one_or_none()
                    if referrer and referrer.telegram_id != telegram_id:
                        user.referred_by = referrer.telegram_id
                        referrer.referral_count = (referrer.referral_count or 0) + 1
                        if referrer.referral_count % 2 == 0:
                            referrer.is_premium = True
                            referrer.premium_expires = datetime.utcnow() + timedelta(days=30)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            else:
                user.last_active = datetime.utcnow()
                user.full_name = full_name
                if username:
                    user.username = username
                await session.commit()
            return user
""").lstrip()

wf("utils/db_api/crud.py", crud)
print("crud start written")
