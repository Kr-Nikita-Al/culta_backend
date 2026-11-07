import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, event
from db import ImageDB, StorageMoveDB
from image.actions.create_image_action import __create_image
from image.directory_move import rename_image_directory
from tests.integration.test_image_quotas import body

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('failure', ['none', 'copy', 'commit'])
def test_directory_paths_change_together_and_preserve_nesting(pg, failure):
    async def scenario():
        root = f"company_images/company_{pg.ids['company_a']}/"
        paths = [root+'tea/', root+'tea/nested/', root+'tea-old/', root+'other/tea/']
        ids = []
        for path in paths:
            request = body(pg)
            request.file_path = path
            async with pg.sessions() as session:
                image = await __create_image(request, pg.ids['admin_a'], session)
                ids.append(image.image_id)
        manifest = [{'source':root+'tea/a.png', 'destination':root+'new/a.png'}]
        async def copy(*args, before_copy):
            await before_copy(manifest)
            if failure == 'copy':
                raise HTTPException(503, 'Copy failed')
            return manifest
        storage = SimpleNamespace(rename_directory=AsyncMock(side_effect=copy))
        request = SimpleNamespace(company_id=pg.ids['company_a'], dir_path=root,
                                  old_dir_name='tea/', new_dir_name='new/')
        async with pg.sessions() as session:
            if failure == 'commit':
                def fail(_): raise RuntimeError('Commit failed')
                event.listen(session.sync_session, 'before_commit', fail)
            if failure == 'none':
                assert set(await rename_image_directory(session, request, storage)) == set(ids[:2])
            else:
                with pytest.raises((RuntimeError, HTTPException)):
                    await rename_image_directory(session, request, storage)
        async with pg.sessions() as session:
            rows = dict((await session.execute(select(ImageDB.image_id, ImageDB.file_path))).all())
            journal = (await session.scalars(select(StorageMoveDB))).all()
            assert len(journal) == 1
            if journal:
                assert journal[0].status == ('committed' if failure == 'none' else 'pending')
                assert journal[0].kind == 'directory'
                assert journal[0].company_id == pg.ids['company_a']
                assert journal[0].copied_keys == manifest
        expected = [root+'new/', root+'new/nested/', *paths[2:]] if failure == 'none' else paths
        assert [rows[key] for key in ids] == expected
        storage.rename_directory.assert_awaited_once()
    asyncio.run(scenario())
