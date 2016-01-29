"""Third party Python libraries.

Third party libraries are placed here when they are not available on the platform by normal means.

FlashAirMusic is a service and not a library. It is intended to be installed through the platform's packaging system
(e.g. RPM files). Because of this some dependencies of FlashAirMusic may not be available in all platforms.

This directory mitigates the problem by allowing packaging scripts to place third party libraries here. This directory
is added to `sys.path` which allows Python to find those libraries here since they won't be installed on the system.
"""
