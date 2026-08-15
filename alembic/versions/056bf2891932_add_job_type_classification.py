"""add job_type classification

Revision ID: 056bf2891932
Revises: f3ee8d52641f
Create Date: 2026-08-15 13:48:52.428923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '056bf2891932'
down_revision: Union[str, Sequence[str], None] = 'f3ee8d52641f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Exact 95 test job IDs from production database audit
TEST_JOB_IDS = [
    'ae4dc179-7de5-4c96-9a44-a87037631adc',
    'd1c15e2a-16be-409c-9c27-535a01d13a68',
    'a329a3c2-ad5b-4038-b2e8-418f92c1379d',
    '32eba66e-c27d-4581-9d49-aa40d64dbe0d',
    'f78aa431-e34e-4d13-a5b3-bc941407cfb7',
    'f36f8942-01f2-492c-9ad3-dfdb35cbd557',
    'ca29b872-951c-4a16-b636-f506f553c441',
    '560c0f92-d365-470e-8109-9fbd12ad8486',
    'a108e5af-6f4f-45cd-adf1-ff1dd4945250',
    '13903b21-660a-42b7-ac6d-14715c53af67',
    '8c61dc20-75e3-4b5b-a2f7-595e879a2db9',
    'ba52c3fe-8e35-400a-838f-3e0bf6e3cfe3',
    'd29d1c8c-45f4-45de-997a-891c000a7c43',
    '4c37ac28-eee9-4e6a-bca9-3ebd4e074ba2',
    '1aaf4e50-b12c-4595-878d-8f5ebfc11436',
    '792d6b27-e252-409e-add7-b206a3fe6191',
    'b77a3c3a-518b-4c2d-9c36-51de9ecfa841',
    '995b27e1-96f9-4882-926a-65d70c0829da',
    '6ecc7340-ca5f-4293-b21d-67645d75c958',
    'd0e9f9b3-adc8-49bf-99de-7f048895c179',
    '1f095bb9-37df-4c04-a521-f9fcb7865e40',
    '20398b35-20b5-4a41-80f9-a87536239617',
    '7077f2c0-14ee-4adb-88e3-61c4e5155e22',
    'f47676c5-2544-4016-bfee-da6eb80b6a06',
    'd9a608f9-ef6d-4254-8710-b388d3c69a35',
    '61171c47-1a80-4054-ab5b-8406583c32ac',
    '7d1d3ab7-43cb-47f1-9b11-8d3c4cfa7e96',
    '4a5b2a18-457f-43fb-9446-ecce599246d0',
    'fd149598-1b67-4dde-a361-b4eba5e65aa6',
    '4bdb5251-0e6f-43cc-8d3c-3be125e5d196',
    '16d097b8-58b2-4ace-8310-134ed20c4371',
    '6024eb4b-f293-4542-aa33-001158775f81',
    'b5f8f4b4-84da-48d5-9aef-f495f99b235d',
    '5f5cb470-d5ea-4764-afef-ac1f72bdb03f',
    '3a2845c3-894e-4e63-bf47-02b5a549611c',
    'e5e1e7b8-666c-4d4a-b617-9fcf84885741',
    'd597304b-4768-4f23-ac25-1aeb008bf2a4',
    '014bb867-6f3e-43b6-9fec-f6f051f4180d',
    '21944875-2384-437a-aae7-05e239e863c7',
    '948c7043-201d-48b1-8149-174ed6fd27ee',
    '3132e17c-c76f-4c13-8ade-5834c18ffb75',
    'a3932074-475b-4c8d-b15d-54adb964f04d',
    '30139a8c-899f-4310-8e56-c67bd1542882',
    '6037692a-07c5-4623-8f0c-d4ab8d89cbd7',
    '7734bebf-df7b-41aa-aa04-4dcd04af473f',
    '610e0b9c-d4f9-43a9-baf7-a19edf66d459',
    '29089bdd-6ad7-4090-aa7c-6e96909cdd51',
    'ea6c566d-0c35-4df0-a805-17777945e8ec',
    '85de6c88-e7da-4e0b-ab78-b22ad4ad8668',
    'f86e448f-2df1-467c-a9bd-835866fe8669',
    '9fb92366-4d99-43cb-9ed8-d09a41f4ac0e',
    'cd5e080f-6704-4255-bf92-76bc09beba6f',
    '0e1d7666-afa9-4e6a-8ea0-7e4cfc26fe9d',
    '98003863-c199-45b2-b156-11e82d63602e',
    '7065a3e2-e235-4a19-aa57-15bf3cb820d9',
    'a2d202fe-482a-4757-975d-7a10c97b064f',
    'a8b3d9cb-f2d9-4a48-adba-80b2ba59d60d',
    '24fc4a3f-f873-4fc5-a286-a66011aab9e8',
    '3817df33-ee58-49b2-b790-1f3b038892ae',
    'c2581e4a-a798-46c9-a9e7-bc185996c661',
    '875c5b13-7418-44c8-8011-fce34dc93c8c',
    '3ff8aebc-e77f-48ba-9466-b6bdd99a4b83',
    'daa6b6e0-df4a-4ed3-9fcd-7352fc62f435',
    '9134ea8d-f953-45b5-855b-fb95e10f1cde',
    '98de4d11-baa5-4787-a520-05706c0a0c46',
    '5a5883c7-f76d-4772-9629-8b6b6ec485fa',
    '248e8f88-bea4-45d6-b913-3d1c1bdd0630',
    'fc10b4cc-b43f-49b1-976e-68e2d8623a5b',
    '391af7db-1c3f-418e-9c72-e38c3cd1e87f',
    '30b3f5bd-2189-4786-a2ec-1b703be38777',
    '86a817a4-c913-41e1-9ba2-dac356c70df0',
    'e2a5b524-d3b8-4c88-80f3-d1ad9cba7da9',
    '28f7040c-1962-4a17-a866-a0f7b74736d4',
    'f4037339-1db2-4ad1-a608-4ea96b1a8934',
    'd8b5f08b-17da-4631-bc5f-bfa5363bf207',
    'b0e61e15-6ea3-4fce-8fc6-1edb7d3fc198',
    '7b5fb701-11c9-45c4-980f-0d9b332908b2',
    '0b763f00-a291-42aa-a90d-9b5019f629f7',
    'fb5ea51d-c2d5-4aa5-8cff-84a0d5fb6ef2',
    'b55acefd-34a2-4bf1-bf39-02af7ddb18f8',
    'aa79d225-4513-4cbd-b5c9-91fb32e55384',
    '926cb5b5-ebcc-4960-b53b-83c3603aecea',
    '22d3cda2-25ee-45fc-850e-303078f2918b',
    'da279ee7-15c0-4a69-91ac-08921ffd00e3',
    'fd63406e-ff5e-4ed0-8c28-e10ec7ba7fb0',
    '16cef779-2b45-4ded-a273-71ceefe15d71',
    '1c1d4fd7-2977-4f0b-8185-efb2a79641c1',
    '95a87f6d-465d-4c3f-9bad-6bb419c2b34e',
    '07a5444c-6f9f-4e48-bb7b-342150c6a31b',
    '6165277d-4017-49df-89b7-e48b50ec0786',
    'be64b7ce-7689-44cb-b6ba-33e9ae323dee',
    '35415e4e-03d4-4086-9029-03ff6a566183',
    'bb2204d5-a466-40a1-bdb0-120070275e0c',
    '6b347f84-04a3-436f-ac56-64bae31178a0',
    '9e821c45-c098-49ee-aae4-b971d66a67be',
]

PROD_JOB_ID = '075db687-8fe5-49e2-baad-94310a8c7da3'

TEST_JOB_IDS_SQL = ','.join(f"'{id}'" for id in TEST_JOB_IDS)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # SAFETY CHECK 1: Verify total jobs = 96
    total_jobs = conn.execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar()
    if total_jobs != 96:
        raise RuntimeError(f"SAFETY CHECK FAILED: Expected 96 total jobs, found {total_jobs}. Migration aborted.")

    # SAFETY CHECK 2: Verify all 95 test IDs exist
    test_count = conn.execute(
        sa.text(f"SELECT COUNT(*) FROM jobs WHERE id IN ({TEST_JOB_IDS_SQL})")
    ).scalar()
    if test_count != 95:
        raise RuntimeError(f"SAFETY CHECK FAILED: Expected 95 test job IDs, found {test_count}. Migration aborted.")

    # SAFETY CHECK 3: Verify production job exists
    prod_count = conn.execute(
        sa.text(f"SELECT COUNT(*) FROM jobs WHERE id = '{PROD_JOB_ID}'")
    ).scalar()
    if prod_count != 1:
        raise RuntimeError(f"SAFETY CHECK FAILED: Production job {PROD_JOB_ID} not found. Migration aborted.")

    # SAFETY CHECK 4: Verify no overlap
    overlap = conn.execute(
        sa.text(f"SELECT COUNT(*) FROM jobs WHERE id = '{PROD_JOB_ID}' AND id IN ({TEST_JOB_IDS_SQL})")
    ).scalar()
    if overlap != 0:
        raise RuntimeError("SAFETY CHECK FAILED: Production job ID found in test IDs. Migration aborted.")

    # 1. Add nullable job_type column
    op.add_column('jobs', sa.Column('job_type', sa.String(16), nullable=True))

    # 2. Update test jobs to 'test'
    conn.execute(
        sa.text(f"UPDATE jobs SET job_type = 'test' WHERE id IN ({TEST_JOB_IDS_SQL})")
    )

    # 3. Update production job to 'production'
    conn.execute(
        sa.text(f"UPDATE jobs SET job_type = 'production' WHERE id = '{PROD_JOB_ID}'")
    )

    # SAFETY CHECK 5: Verify no NULL job_type remains
    null_count = conn.execute(sa.text("SELECT COUNT(*) FROM jobs WHERE job_type IS NULL")).scalar()
    if null_count != 0:
        raise RuntimeError(f"SAFETY CHECK FAILED: {null_count} jobs still have NULL job_type. Migration aborted.")

    # SAFETY CHECK 6: Verify counts
    prod_final = conn.execute(sa.text("SELECT COUNT(*) FROM jobs WHERE job_type = 'production'")).scalar()
    test_final = conn.execute(sa.text("SELECT COUNT(*) FROM jobs WHERE job_type = 'test'")).scalar()
    if prod_final != 1:
        raise RuntimeError(f"SAFETY CHECK FAILED: Expected 1 production job, found {prod_final}. Migration aborted.")
    if test_final != 95:
        raise RuntimeError(f"SAFETY CHECK FAILED: Expected 95 test jobs, found {test_final}. Migration aborted.")

    # 4. Make non-nullable with server_default
    op.alter_column('jobs', 'job_type', nullable=False, server_default='production')

    # 5. Add CHECK constraint
    op.create_check_constraint('ck_job_type', 'jobs', "job_type IN ('production', 'test')")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_job_type', 'jobs', type_='check')
    op.drop_column('jobs', 'job_type')