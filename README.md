# Laubwerk Importer for Blender #

This project implements a Python plugin to import Laubwerk plant models into Blender. It facilitates the Python Extension delivered with all versions of the Laubwerk Player Plugin. It can be used with all Laubwerk Plants Kits, including the [Laubwerk Plants Kit Freebie](http://www.laubwerk.com/store/plants-kit-freebie).

### What is this repository for? ###

This repository contains the latest version of the plugin and can be used to contribute improvements.

### How do I get set up? ###

**Prerequisites**

* You will need to have the Laubwerk Player Plugin (which is part of every Laubwerk Plants Kit) installed, so the Laubwerk Python Extension is available. If you do not have Laubwerk Plants already installed, you can grab the Plants Kit Freebie [from the Laubwerk website](http://www.laubwerk.com/store/plants-kit-freebie). Keep in mind, that the Laubwerk Python Extension is currently only available on Windows.
* A current version of [Blender](http://www.blender.org/). The plugin is known to run with [Blender 2.72](http://www.blender.org/features/past-releases/2-72/).

**Installation (only Windows at the moment)**

* After Blender has been started at least once, there will be a folder *%AppData%/Blender Foundation/2.72/scripts/addons*. Clone the git repository into that folder, but change the name of the Repository folder to *io_import_laubwerk*.
* When restarting Blender, it will see the plugin, but it will be disabled by default. Choose *File* -> *User Preferences...* to bring up the Preferences window. Select the *Addons* Tab and look for the Laubwerk Addon in the list (search for *laubwerk*). Enabling the checkbox will load the Addon.
* Clicking the *Save User Settings* button at the bottom of the Preferences window makes sure Blender remembers this setting.
* After you did this, the Laubwerk import Addon is available through *File* -> *Import* -> *Laubwerk Plant (.lbw.gz)*. 
* More general information about Blender Add-Ons can be found [here](http://wiki.blender.org/index.php/Doc:2.6/Manual/Extensions/Python/Add-Ons).

### Who do I talk to? ###

* Repository Owner: Fabian Quosdorf (<fabian@faqgames.net>)
