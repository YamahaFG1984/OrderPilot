from orderpilot.platform.integrations.models import SyncJob
from orderpilot.platform.integrations.services import run_sync_job
from orderpilot.trade.masterdata.models import Customer, Product, Supplier


def _pull():
    job = SyncJob.objects.create(system="kingdee", entity="masterdata", direction="pull")
    return run_sync_job(job)


def test_masterdata_sync_is_idempotent(db):
    job = _pull()
    assert job.status == SyncJob.Status.SUCCESS, job.error
    assert Supplier.objects.count() == 3
    assert Customer.objects.count() == 2
    assert Product.objects.count() == 10
    # 金蝶里禁用的物料同步为废番
    assert Product.objects.get(part_no="HM-TW-OLD1").status == Product.Status.DISCONTINUED
    assert Product.objects.get(part_no="JB-BT-350").default_supplier.code == "VEN0002"

    job2 = _pull()
    assert job2.status == SyncJob.Status.SUCCESS
    assert Supplier.objects.count() == 3 and Product.objects.count() == 10
    assert job2.stats.get("商品未变") == 10


def test_sync_failure_is_recorded(db, settings):
    settings.ORDERPILOT_ERP_ADAPTER = "orderpilot.does_not_exist.Adapter"
    job = _pull()
    assert job.status == SyncJob.Status.FAILED
    assert "does_not_exist" in job.error
