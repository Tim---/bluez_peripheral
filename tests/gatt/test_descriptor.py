from dbus_next import introspection
from unittest import IsolatedAsyncioTestCase
import re

from dbus_next.signature import Variant

from tests.util import BusManager, MockAdapter, get_attrib

from bluez_peripheral.util import get_message_bus
from bluez_peripheral.gatt.characteristic import characteristic
from bluez_peripheral.gatt.descriptor import DescriptorFlags, descriptor
from bluez_peripheral.gatt.service import Service

last_opts = None
write_desc_val = None


class TestService(Service):
    def __init__(self):
        super().__init__("180A")

    @characteristic("2A37")
    def some_char(self, _):
        pass

    @some_char.descriptor("2A38")
    def read_only_desc(self, opts):
        global last_opts
        last_opts = opts
        return bytes("Test Message", "utf-8")

    @descriptor("2A39", some_char, DescriptorFlags.WRITE)
    def write_desc(self, _):
        pass

    @write_desc.setter
    def write_desc(self, val, opts):
        global last_opts
        last_opts = opts
        global write_desc_val
        write_desc_val = val


class TestDescriptor(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._client_bus = await get_message_bus()
        self._bus_manager = BusManager()
        self._path = "/com/spacecheese/bluez_peripheral/test_descriptor"

    async def asyncTearDown(self):
        self._bus_manager.close()
        self._client_bus.disconnect()

    async def test_structure(self):
        async def inspector(path):
            char = await get_attrib(
                self._client_bus, self._bus_manager.name, path, "180A", char_uuid="2A37"
            )

            child_names = [path.split("/")[-1] for path in char.child_paths]
            child_names = sorted(child_names)

            i = 0
            for name in child_names:
                assert re.match(r"^descriptor0{0,2}" + str(i) + "$", name)
                i += 1

        service = TestService()
        adapter = MockAdapter(inspector)

        await service.register(self._bus_manager.bus, self._path, adapter)

    async def test_read(self):
        async def inspector(path):
            global last_opts
            opts = {
                "offset": Variant("q", 0),
                "link": Variant("s", "dododo"),
                "device": Variant("s", "bebealbl/.afal"),
            }
            interface = (
                await get_attrib(
                    self._client_bus,
                    self._bus_manager.name,
                    path,
                    "180A",
                    char_uuid="2A37",
                    desc_uuid="2A38",
                )
            ).get_interface("org.bluez.GattDescriptor1")
            resp = await interface.call_read_value(opts)

            assert resp.decode("utf-8") == "Test Message"
            assert last_opts.offset == 0
            assert last_opts.link == "dododo"
            assert last_opts.device == "bebealbl/.afal"

        service = TestService()
        adapter = MockAdapter(inspector)

        await service.register(self._bus_manager.bus, self._path, adapter)

    async def test_write(self):
        async def inspector(path):
            global last_opts
            global write_desc_val
            opts = {
                "offset": Variant("q", 1),
                "device": Variant("s", "bebealbl/.afal"),
                "link": Variant("s", "gogog"),
                "prepare-authorize": Variant("b", True),
            }
            interface = (
                await get_attrib(
                    self._client_bus,
                    self._bus_manager.name,
                    path,
                    "180A",
                    char_uuid="2A37",
                    desc_uuid="2A39",
                )
            ).get_interface("org.bluez.GattDescriptor1")
            await interface.call_write_value(bytes("Test Write Value", "utf-8"), opts)

            assert last_opts.offset == 1
            assert last_opts.device == "bebealbl/.afal"
            assert last_opts.link == "gogog"
            assert last_opts.prepare_authorize == True

            assert write_desc_val.decode("utf-8") == "Test Write Value"

        service = TestService()
        adapter = MockAdapter(inspector)

        await service.register(self._bus_manager.bus, self._path, adapter)
