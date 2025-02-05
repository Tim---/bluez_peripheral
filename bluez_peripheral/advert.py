from dbus_next.aio import MessageBus
from dbus_next.aio.proxy_object import ProxyInterface
from dbus_next.constants import PropertyAccess
from dbus_next.service import ServiceInterface, method, dbus_property

from enum import Enum, Flag, auto
from typing import Collection, Dict, Union
import struct

from .uuid import BTUUID
from .util import *


class PacketType(Enum):
    BROADCAST = 0
    """The relevant service(s) will be broadcast and do not require pairing.
    """
    PERIPHERAL = 1
    """The relevant service(s) are associated with a peripheral role.
    """


class AdvertisingIncludes(Flag):
    NONE = 0
    TX_POWER = auto()
    """Transmittion power should be included.
    """
    APPEARANCE = auto()
    """Device appearance number should be included.
    """
    LOCAL_NAME = auto()
    """The local name of this device should be included.
    """


class Advertisement(ServiceInterface):
    """
    An advertisment for a particular service or collection of services that can be registered and broadcast to nearby devices.

    Args:
        localName (str): The device name to advertise.
        serviceUUIDs (Collection[Union[BTUUID, str]]): A list of service UUIDs advertise.
        appearance (Union[int, bytes]): The appearance value to advertise.
            `See the Bluetooth SIG recognised values. <https://specificationrefs.bluetooth.com/assigned-values/Appearance%20Values.pdf>`_
        timeout (int): The time from registration until this advert is removed.
        discoverable (bool, optional): Whether or not the device this advert should be general discoverable.
        packet_type (PacketType, optional): The type of advertising packet requested.
        manufacturerData (Dict[int, bytes], optional): Any manufacturer specific data to include in the advert.
        solicitUUIDs (Collection[BTUUID], optional): Array of service UUIDs to attempt to solicit (not widely used).
        serviceData (Dict[str, bytes], optional): Any service data elements to include.
        includes (AdvertisingIncludes, optional): Fields that can be optionally included in the advertising packet.
            Only the :class:`AdvertisingIncludes.TX_POWER` flag seems to work correctly with bluez.
        duration (int, optional): Duration of the advert when multiple adverts are ongoing.
    """

    _INTERFACE = "org.bluez.LEAdvertisement1"
    _MANAGER_INTERFACE = "org.bluez.LEAdvertisingManager1"

    def __init__(
        self,
        localName: str,
        serviceUUIDs: Collection[Union[BTUUID, str]],
        appearance: Union[int, bytes],
        timeout: int,
        discoverable: bool = True,
        packet_type: PacketType = PacketType.PERIPHERAL,
        manufacturerData: Dict[int, bytes] = {},
        solicitUUIDs: Collection[BTUUID] = [],
        serviceData: Dict[str, bytes] = {},
        includes: AdvertisingIncludes = AdvertisingIncludes.NONE,
        duration: int = 2,
    ):
        self._type = packet_type
        # Convert any string uuids to uuid16.
        self._serviceUUIDs = [
            uuid if type(uuid) is BTUUID else BTUUID.from_uuid16(uuid)
            for uuid in serviceUUIDs
        ]
        self._localName = localName
        # Convert the appearance to a uint16 if it isn't already an int.
        self._appearance = (
            appearance if type(appearance) is int else struct.unpack("H", appearance)[0]
        )
        self._timeout = timeout

        self._manufacturerData = manufacturerData
        self._solicitUUIDs = solicitUUIDs
        self._serviceData = serviceData
        self._discoverable = discoverable
        self._includes = includes
        self._duration = duration

        super().__init__(self._INTERFACE)

    async def register(
        self,
        bus: MessageBus,
        adapter: Adapter = None,
        path: str = "/com/spacecheese/bluez_peripheral/advert0",
    ):
        """Register this advert with bluez to start advertising.

        Args:
            bus (MessageBus): The message bus used to communicate with bluez.
            adapter (Adapter, optional): The adapter to use.
            path (str, optional): The dbus path to use for registration.
        """
        # Export this advert to the dbus.
        bus.export(path, self)

        if adapter is None:
            adapter = await Adapter.get_first(bus)

        # Get the LEAdvertisingManager1 interface for the target adapter.
        interface = adapter._proxy.get_interface(self._MANAGER_INTERFACE)
        await interface.call_register_advertisement(path, {})

        bus.unexport(path, self._INTERFACE)

    @classmethod
    async def GetSupportedIncludes(cls, adapter: Adapter) -> AdvertisingIncludes:
        interface = adapter._proxy.get_interface(cls._MANAGER_INTERFACE)
        includes = await interface.get_supported_includes()
        flags = AdvertisingIncludes.NONE
        for inc in includes:
            inc = AdvertisingIncludes[kebab_to_shouting_snake(inc)]
            # Combine all the included flags.
            flags |= inc
        return flags

    @method()
    def Release(self):  # type: ignore
        return

    @dbus_property(PropertyAccess.READ)
    def Type(self) -> "s":  # type: ignore
        return self._type.name.lower()

    @dbus_property(PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":  # type: ignore
        return [id.uuid16 for id in self._serviceUUIDs]

    @dbus_property(PropertyAccess.READ)
    def LocalName(self) -> "s":  # type: ignore
        return self._localName

    @dbus_property(PropertyAccess.READ)
    def Appearance(self) -> "q":  # type: ignore
        return self._appearance

    @dbus_property(PropertyAccess.READ)
    def Timeout(self) -> "q":  # type: ignore
        return self._timeout

    @dbus_property(PropertyAccess.READ)
    def ManufacturerData(self) -> "a{qay}":  # type: ignore
        return self._manufacturerData

    @dbus_property(PropertyAccess.READ)
    def SolicitUUIDs(self) -> "as":  # type: ignore
        return [id.uuid16 for id in self._solicitUUIDs]

    @dbus_property(PropertyAccess.READ)
    def ServiceData(self) -> "a{say}":  # type: ignore
        return self._serviceData

    @dbus_property(PropertyAccess.READ)
    def Discoverable(self) -> "b":  # type: ignore
        return self._discoverable

    @dbus_property(PropertyAccess.READ)
    def Includes(self) -> "as":  # type: ignore
        return [
            snake_to_kebab(inc.name)
            for inc in AdvertisingIncludes
            if self._includes & inc
        ]

    @dbus_property(PropertyAccess.READ)
    def Duration(self) -> "q":  # type: ignore
        return self._duration
