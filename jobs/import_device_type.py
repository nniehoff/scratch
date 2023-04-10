"""Job to import DeviceType from a Github repository."""
import requests
import yaml

from nautobot.extras.jobs import Job
from nautobot.extras.jobs import BooleanVar, StringVar

from nautobot.dcim.forms import DeviceTypeImportForm
from nautobot.dcim.models import (
    ConsolePortTemplate,
    ConsoleServerPortTemplate,
    DeviceBayTemplate,
    FrontPortTemplate,
    InterfaceTemplate,
    PowerOutletTemplate,
    PowerPortTemplate,
    RearPortTemplate,
    DeviceType,
)

DEFAULT_REPO = "netbox-community/devicetype-library"
DEFAULT_BRANCH = "master"

COMPONENTS = {
    "console-ports": ConsolePortTemplate,
    "console-server-ports": ConsoleServerPortTemplate,
    "power-ports": PowerPortTemplate,
    "power-outlets": PowerOutletTemplate,
    "interfaces": InterfaceTemplate,
    "rear-ports": RearPortTemplate,
    "front-ports": FrontPortTemplate,
    "device-bays": DeviceBayTemplate,
}


name = "Gizmo Jobs"


def import_device_type(data):
    """Import DeviceType."""
    slug = data.get("slug")

    try:
        devtype = DeviceType.objects.get(slug=data.get("slug"))
        raise ValueError(f"Unable to import this device_type, a DeviceType with this slug ({slug}) already exist.")
    except DeviceType.DoesNotExist:
        pass

    dtif = DeviceTypeImportForm(data)
    devtype = dtif.save()

    # Import All Components
    for key, component_class in COMPONENTS.items():
        if key in data:
            component_list = []
            for item in data[key]:
                component_list.append(component_class(device_type=devtype, **item))
            component_class.objects.bulk_create(component_list)

    return devtype


class ImportDeviceType(Job):
    """Job to import DeviceType from a Github repository."""

    class Meta:
        """Meta class for ImportDeviceType."""

        name = "Import Device Type"
        description = "Import a new Device Type from a GitHub repository"

    repository = StringVar(default=DEFAULT_REPO)
    master = StringVar(default=DEFAULT_BRANCH)
    device_type = StringVar()

    def run(self, data=None, commit=None):
        """Main function for ImportDeviceType."""
        repository = data.get("repository", DEFAULT_REPO)
        branch = data.get("branch", DEFAULT_BRANCH)
        device_type = data.get("device_type", "none.yaml")
        url = f"https://raw.githubusercontent.com/{repository}/{branch}/device-types/{device_type}.yaml"
        resp = requests.get(url)
        resp.raise_for_status()

        data = yaml.safe_load(resp.text)

        if "slug" not in data:
            self.log_error("The data returned is not valid, it should be a valid DeviceType in YAML format")
            return False

        slug = data.get("slug")
        try:
            devtype = import_device_type(data)
        except ValueError as exc:
            if "already exist" not in str(exc):
                raise
            else:
                self.log_warning(
                    message=f"Unable to import {device_type}, a DeviceType with this slug ({slug}) already exist."
                )
                return False

        self.log_success(devtype, f"Imported DeviceType {slug} successfully")
