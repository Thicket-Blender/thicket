# Laubwerk Plants for Blender
Laubwerk Plants for Blender is a [Blender](http://www.blender.org) Add-on to import [Laubwerk Plants](http://www.laubwerk.com) high resolution plant and tree models.

This project is an updated fork of https://bitbucket.org/laubwerk/lbwbl.

![doc/acerp-cycles.png](doc/acerp-cycles.png)

## How do I get set up?
### Prerequisites
* [Blender](http://www.blender.org/) 2.80 or later. The plugin is known to run with [Blender 2.81a](http://www.blender.org/features/past-releases/2-81/).
* Laubwerk Player Plugin, which includes the Python SDK, available in all Laubwerk Plant Kits, including the [Plants Kit Freebie](http://www.laubwerk.com/store/plants-kit-freebie).
  * NOTE: The Python 3 version of the SDK is required. This is currently under development and is not included in the plant kits. For now, you can email Laubwerk requesting access (see the footer at [laubwerk.com](http://www.laubwerk.com) for contact information).

### Installation
* After Blender has been started at least once the addon folder will have been created. Clone the git repository into that folder and change the name of the repository folder to `io_import_laubwerk`.
  * Mac: `~/Library/Blender/2.80/scripts/addons`
  * Windows: `%AppData%/Blender Foundation/2.80/scripts/addons` (TODO: verify)
* When restarting Blender, it will see the plugin, but it will be disabled by default. Choose `Edit -> Preferences...` to bring up the Preferences window. Select the `Add-ons` tab and look for `Import: Laubwerk Plants Importer` in the list (search for `laubwerk`). Check the box to enable the add-on.
* Click the twisty to expand the addon preferences. Enter the Laubwerk install path and click `Rebuild Database`. This will take a few minutes depending on your computer to scan your Laubwerk Plants files and populate the database.
![doc/lbwbl-prefs.png](doc/lbwbl-prefs.png)
* After you did this, the Laubwerk Add-on is available through `File -> Import -> Laubwerk Plant (.lbw.gz)`.
* See the Blender Wiki for more general information about [Blender Add-ons](https://wiki.blender.org/wiki/Process/Addons).

### Who do I talk to? ###
See [CONTRIBUTING](CONTRIBUTING.md) for more information.
