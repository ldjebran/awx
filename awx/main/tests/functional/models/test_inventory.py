import pytest
import mock

# AWX
from awx.main.models import (
    Host,
    Inventory,
    InventorySource,
    InventoryUpdate,
)


@pytest.mark.django_db
class TestSCMUpdateFeatures:

    def test_automatic_project_update_on_create(self, inventory, project):
        inv_src = InventorySource(
            source_project=project,
            source_path='inventory_file',
            inventory=inventory,
            update_on_project_update=True,
            source='scm')
        with mock.patch.object(inv_src.source_project, 'update') as mck_update:
            inv_src.save()
            mck_update.assert_called_once_with()

    def test_reset_scm_revision(self, scm_inventory_source):
        starting_rev = scm_inventory_source.scm_last_revision
        assert starting_rev != ''
        scm_inventory_source.source_path = '/newfolder/newfile.ini'
        scm_inventory_source.save()
        assert scm_inventory_source.scm_last_revision == ''

    def test_source_location(self, scm_inventory_source):
        # Combines project directory with the inventory file specified
        inventory_update = InventoryUpdate(
            inventory_source=scm_inventory_source,
            source_path=scm_inventory_source.source_path)
        assert inventory_update.get_actual_source_path().endswith('_92__test_proj/inventory_file')

    def test_no_unwanted_updates(self, scm_inventory_source):
        # Changing the non-sensitive fields should not trigger update
        with mock.patch.object(scm_inventory_source.source_project, 'update') as mck_update:
            scm_inventory_source.name = 'edited_inventory'
            scm_inventory_source.description = "I'm testing this!"
            scm_inventory_source.save()
            assert not mck_update.called


@pytest.fixture
def setup_ec2_gce(organization):
    ec2_inv = Inventory.objects.create(name='test_ec2', organization=organization)

    ec2_source = ec2_inv.inventory_sources.create(name='test_ec2_source', source='ec2')
    for i in range(2):
        ec2_host = ec2_inv.hosts.create(name='test_ec2_{0}'.format(i))
        ec2_host.inventory_sources.add(ec2_source)
    ec2_inv.save()

    gce_inv = Inventory.objects.create(name='test_gce', organization=organization)

    gce_source = gce_inv.inventory_sources.create(name='test_gce_source', source='gce')
    gce_host = gce_inv.hosts.create(name='test_gce_host')
    gce_host.inventory_sources.add(gce_source)
    gce_inv.save()


@pytest.fixture
def setup_inventory_groups(inventory, group_factory):

    groupA = group_factory('test_groupA')
    groupB = group_factory('test_groupB')

    host = Host.objects.create(name='single_host', inventory=inventory)

    groupA.hosts.add(host)
    groupA.save()

    groupB.hosts.add(host)
    groupB.save()


@pytest.mark.django_db
class TestHostManager:
    def test_host_filter_change(self, setup_ec2_gce, organization):
        smart_inventory = Inventory(name='smart',
                                    kind='smart',
                                    organization=organization,
                                    host_filter='inventory_sources__source=ec2')
        smart_inventory.save()
        assert len(smart_inventory.hosts.all()) == 2

        smart_inventory.host_filter = 'inventory_sources__source=gce'
        smart_inventory.save()
        assert len(smart_inventory.hosts.all()) == 1

    def test_host_filter_not_smart(self, setup_ec2_gce, organization):
        smart_inventory = Inventory(name='smart',
                                    organization=organization,
                                    host_filter='inventory_sources__source=ec2')
        assert len(smart_inventory.hosts.all()) == 0

    def test_host_objects_manager(self, setup_ec2_gce, organization):
        smart_inventory = Inventory(kind='smart',
                                    name='smart',
                                    organization=organization,
                                    host_filter='inventory_sources__source=ec2')
        smart_inventory.save()

        hosts = smart_inventory.hosts.all()
        assert len(hosts) == 2
        assert hosts[0].inventory_sources.first().source == 'ec2'
        assert hosts[1].inventory_sources.first().source == 'ec2'

    def test_host_objects_no_dupes(self, setup_inventory_groups, organization):
        smart_inventory = Inventory(name='smart',
                                    kind='smart',
                                    organization=organization,
                                    host_filter='groups__name=test_groupA or groups__name=test_groupB')
        smart_inventory.save()
        assert len(smart_inventory.hosts.all()) == 1
