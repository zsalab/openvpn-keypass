ovpn_keypass for macOS
=======================

This folder contains:
  - ovpn_keypass          the command-line tool
  - ovpn_keypass_gui.app  the graphical version

IMPORTANT: Gatekeeper warning on first run
-------------------------------------------
These binaries are only ad-hoc signed, not notarized by Apple (that
needs a paid Apple Developer account), so macOS will likely refuse to
open them the first time with a message like:

  "ovpn_keypass_gui" cannot be opened because Apple could not verify
  it is free of malware that may harm your Mac or compromise your
  privacy.

This is standard macOS behavior for any app downloaded from outside
the App Store that isn't notarized — it does not mean the app is
unsafe. To run it anyway, do ONE of the following:

1. Terminal (recommended, works every time):
   Open Terminal, "cd" into this folder, and run:

     xattr -cr ovpn_keypass_gui.app
     xattr -cr ovpn_keypass

   This clears the quarantine flag macOS set when you downloaded the
   file. You can now open the app or run the CLI tool normally.

2. System Settings:
   Try to open the app once (it will be blocked), then go to
   System Settings -> Privacy & Security, scroll down to the blocked
   app notice near the bottom, and click "Open Anyway".

Using the CLI tool
-------------------
  ./ovpn_keypass --help

Using the GUI
--------------
  Double-click ovpn_keypass_gui.app (after clearing quarantine above).

Full documentation and source: https://github.com/zsalab/openvpn-keypass
