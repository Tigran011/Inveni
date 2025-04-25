# Inveni - File Version Manager

**Version**: 1.0  
**Author**: [Tigran](https://github.com/Tigran011)  

---

## Overview

Inveni is a **File Version Manager** designed to make file tracking and versioning simple, seamless, and reliable. It is ideal for individuals and teams who need to maintain backups, manage file versions, and ensure data integrity. With a clean codebase, Inveni is also highly customizable for developers to adapt and extend.

---

## Key Features

- **Automatic File Tracking**: Monitor changes in files and maintain version histories.
- **Backup Management**: Secure your data with automatic backups.
- **System Tray Integration**: Minimize to the tray for non-intrusive background operation.
- **Customizable and Open Source**: Modify and extend the app to meet specific needs.
- **Cross-Platform**: Available as both an installer and a portable version.

---

## Installation

### Using the Installer

1. Download the **installer** from the [Releases Page](https://github.com/Tigran011/Inveni/releases).
2. Run the installer and follow the setup wizard instructions.
3. Launch Inveni from the **Start Menu** or **Desktop Shortcut** after installation.

### Using the Portable Version

1. Download the **portable version** from the [Releases Page](https://github.com/Tigran011/Inveni/releases).
2. Extract the ZIP file to a location of your choice.
3. Run `Inveni.exe` to launch the application without installation.

---

## Usage

1. **File Monitoring**:
   - Add files or directories to be monitored using the "Add File/Folder" option in the app.
   - Inveni will track changes and automatically create backups.

2. **Version Management**:
   - Select a file in the main window to view its version history.
   - Restore or preview any previous version.

3. **System Tray**:
   - Inveni runs in the background and minimizes to the system tray for convenience.
   - Right-click the tray icon for quick actions like opening the app or viewing recent files.

4. **Customization**:
   - Adjust settings such as backup location, file monitoring preferences, and more through the settings menu.

---

## Developer Notes

### Code Structure

Inveni's codebase is designed with modularity and extensibility in mind:

- **Core**: Handles settings, version management, and backups.
- **UI**: Manages the graphical interface and user interactions.
- **Shared State**: Centralized state management for seamless communication between components.
- **Utils**: Provides utility functions for time management, file type handling, and other helpers.

### How to Contribute

1. Fork the repository at [Inveni on GitHub](https://github.com/Tigran011/Inveni).
2. Clone your forked repository to your local machine.
3. Make your changes to the codebase.
4. Submit a pull request with a clear description of your modifications.

---

## Known Issues

1. **Multiple Instances**:
   - Inveni ensures only one instance runs at a time. If issues arise, ensure all existing instances are closed.
   
2. **File Locking**:
   - Log files may sometimes be locked by the system. Restart the app or system to resolve this.

---

## License

Inveni is licensed under the [GNU General Public License v3.0 (GPL-3.0)](https://www.gnu.org/licenses/gpl-3.0.html).  
This means you are free to use, modify, and distribute the software, provided you comply with the license terms.

---

## Support

For support, feature requests, or bug reports, please open an issue on the [GitHub Repository](https://github.com/Tigran011/Inveni/issues).
Or write me [tigranv001@gmail.com].

---

**Thank you for choosing Inveni!**
