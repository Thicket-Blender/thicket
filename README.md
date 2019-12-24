# Laubwerk Plants for Blender
Laubwerk Plants for Blender is a [Blender](http://www.blender.org) Addon to import [Laubwerk Plants](http://www.laubwerk.com) high resolution plant and tree models.

This project is an updated fork of https://bitbucket.org/laubwerk/lbwbl.

![doc/acerp-cycles.png](doc/acerp-cycles.png)

## How do I get set up?
### Prerequisites
* [Blender](http://www.blender.org/) 2.80 or later. The plugin is known to run with [Blender 2.81a](http://www.blender.org/features/past-releases/2-81/).
* Laubwerk Player Plugin, which includes the Python SDK, available in all Laubwerk Plant Kits, including the [Plants Kit Freebie](http://www.laubwerk.com/store/plants-kit-freebie).
  * NOTE: The Python 3 version of the SDK is required. This is currently under development and is not included in the plant kits. For now, you can email Laubwerk requesting access (see the footer at [laubwerk.com](http://www.laubwerk.com) for contact information).

### Installation
* Ensure the Laubwerk python module is in your PYTHONPATH
  * Mac: PYTHONPATH=/Library/Application Support/Laubwerk/Python
  * Windows: TODO
* After Blender has been started at least once the addon folder will have been created. Clone the git repository into that folder and change the name of the repository folder to `io_import_laubwerk`.
  * Mac: `~/Library/Blender/2.80/scripts/addons`
  * Windows: `%AppData%/Blender Foundation/2.80/scripts/addons` (TODO: verify)
* When restarting Blender, it will see the plugin, but it will be disabled by default. Choose `File -> User Preferences...` to bring up the Preferences window. Select the *Addons* Tab and look for the Laubwerk Addon in the list (search for `laubwerk`). Enabling the checkbox will load the Addon.
* Clicking the `Save User Settings` button at the bottom of the Preferences window makes sure Blender remembers this setting.
* After you did this, the Laubwerk import Addon is available through `File -> Import -> Laubwerk Plant (.lbw.gz)`.
* See the Blender Wiki for more general information about [Blender Addons](https://wiki.blender.org/wiki/Process/Addons).

### Who do I talk to? ###
See [CONTRIBUTING](CONTRIBUTING.md) for more information.
