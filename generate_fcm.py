# Author: Sebastiano Barezzi <barezzisebastiano@gmail.com>
# Version: 1.5 ( mod by isus203)

import io
import re
from pathlib import Path
from typing import Dict, List, Set, Optional

# Custom exceptions for clearer error handling
class EntryError(Exception):
    """Base exception for Entry class errors."""
    pass

class DifferentNameError(EntryError):
    """Raised when trying to merge entries with different names."""
    pass

class DifferentHALTypeError(EntryError):
    """Raised when trying to merge entries with different HAL types."""
    pass

class Version:
    """Represents a HAL version with a major and minor number."""
    def __init__(self, version_str: str):
        try:
            self.major, self.minor = map(int, version_str.split('.'))
        except ValueError:
            raise ValueError(f"Invalid version format: '{version_str}'. Expected 'major.minor'.")

    def merge_version(self, other_version: 'Version'):
        """Merges another version, updating the minor number if it's greater."""
        if self.major != other_version.major:
            return
        if other_version.minor > self.minor:
            self.minor = other_version.minor

    def __repr__(self):
        return f"Version(major={self.major}, minor={self.minor})"
    
    def __str__(self):
        """Formats the version for XML output."""
        if self.minor > 0:
            return f"{self.major}.0-{self.minor}"
        return f"{self.major}.{self.minor}"

class Interface:
    """Represents a HAL interface with a name and instances."""
    def __init__(self, name: str, instance: str):
        self.name = name
        self.instances: Set[str] = {instance}

    def merge_interface(self, other_interface: 'Interface'):
        """Merges another interface's instances."""
        if self.name != other_interface.name:
            return
        self.instances.update(other_interface.instances)

    def __repr__(self):
        return f"Interface(name='{self.name}', instances={self.instances})"

    def format_xml(self) -> str:
        """Formats the interface as an XML string."""
        interface_str = f"    <interface>\n        <name>{self.name}</name>\n"
        for instance in sorted(self.instances): # Sorting for consistent output
            interface_str += f"        <instance>{instance}</instance>\n"
        interface_str += "    </interface>\n"
        return interface_str

class Entry:
    """Represents a single HAL entry, either HIDL or AIDL."""
    def __init__(self, fqname: str):
        self.fqname = fqname.strip()
        self.type: str
        self.name: str
        self.versions: Dict[int, Version] = {}
        self.interfaces: Dict[str, Interface] = {}
        self._parse_fqname()

    def _parse_fqname(self):
        """Parses the FQNAME string to extract data."""
        if "@" in self.fqname:
            self.type = "HIDL"
            hal_info, interface_info = self.fqname.split("::")
            self.name, version_str = hal_info.split("@")
            interface_name, interface_instance = interface_info.split("/", 1)
            version = Version(version_str)
            self.versions[version.major] = version
        else:
            self.type = "AIDL"
            hal_info, interface_info = self.fqname.rsplit(".", 1)
            self.name = hal_info
            interface_name, interface_instance = interface_info.split("/", 1)

        interface = Interface(interface_name, interface_instance)
        self.interfaces[interface.name] = interface

    def merge_entry(self, other_entry: 'Entry'):
        """Merges another Entry object into this one."""
        if self.name != other_entry.name:
            raise DifferentNameError("Cannot merge entries with different names.")
        if self.type != other_entry.type:
            raise DifferentHALTypeError("Cannot merge entries with different HAL types.")

        for major, version in other_entry.versions.items():
            if major in self.versions:
                self.versions[major].merge_version(version)
            else:
                self.versions[major] = version

        for name, interface in other_entry.interfaces.items():
            if name in self.interfaces:
                self.interfaces[name].merge_interface(interface)
            else:
                self.interfaces[name] = interface

    def format_xml(self) -> str:
        """Formats the entry as a full XML block."""
        entry_str = f'<hal format="{self.type.lower()}" optional="true">\n'
        entry_str += f'    <name>{self.name}</name>\n'

        # Sort versions by major number for consistent output
        for version in sorted(self.versions.values(), key=lambda v: v.major):
            entry_str += f"    <version>{version}</version>\n"

        # Sort interfaces by name for consistent output
        for interface in sorted(self.interfaces.values(), key=lambda i: i.name):
            entry_str += interface.format_xml()

        entry_str += '</hal>\n'
        return entry_str

def main():
    """
    Main function to process FQNAMEs and generate the fcm.xml file.
    """
    input_file = Path("fqnames.txt")
    output_file = Path("fcm.xml")
    
    if not input_file.exists():
        print(f"Error: The input file '{input_file}' was not found.")
        return

    entries: Dict[str, Entry] = {}
    versioned_aidl_regex = re.compile(r" \(@[0-9]+\)$")

    with input_file.open("r", encoding="utf-8") as f:
        for line in f:
            fqname = line.strip()

            if not fqname or fqname.startswith('#'):
                continue
            
            # Use re.sub for a clean replacement
            fqname = versioned_aidl_regex.sub("", fqname)

            try:
                entry = Entry(fqname)
                if entry.name in entries:
                    entries[entry.name].merge_entry(entry)
                else:
                    entries[entry.name] = entry
            except (ValueError, IndexError) as e:
                print(f"Skipping invalid line: '{fqname}' - Error: {e}")

    # Generate XML and write to file
    with output_file.open("w", encoding="utf-8") as f:
        for entry in sorted(entries.values(), key=lambda e: e.name):
            f.write(entry.format_xml())

    print(f"File contents of '{output_file}':\n")
    print(output_file.read_text(encoding="utf-8"))
    print("\n")
    print(f"The file '{output_file}' was created successfully.")
    
if __name__ == "__main__":
    main()
