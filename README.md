# Thicket
## Laubwerk Plants Add-on for Blender
Thicket is a [Blender](http://www.blender.org) Add-on to import [Laubwerk Plants](http://www.laubwerk.com) high resolution plant and tree models.

Thicket is a community project developed using the Laubwerk Python3 SDK. While not affiliated with or officially supported by Laubwerk GmbH, this project would not be possible without Laubwerk's efforts to answer questions and address issues during the development of Thicket.

Using Laubwerk's level of detail controls, Thicket keeps the Blender viewport responsive and renderings photo-realistic, like this shot of a Japanese Maple (Acer Palmatum).

![doc/acerp-cycles.png](doc/acerp-cycles.png)

## Features
Thicket generates separate viewport and render models, supporting various levels of detail for each. The viewport can display a low poly proxy (convex hull) or a low detail model in any of Blender's viewport modes. The rendered model geometry is generated using various level of detail controls.

* Separate viewport and render models
* Collection instancing
* Material Nodes
* Viewport model level of detail
  * Proxy (Convex Hull)
  * Low poly model
* Render model level of detail
  * Subdivision
  * Branching level
  * Leaf density
  * Branch thickness
* Sidebar `Thicket` panel to change these options after import

![doc/thicket-banner-2048.png](doc/thicket-banner-2048.png)

## Install
Thicket is in active development toward the initial 1.0 release, which will
include installers for download. Until then, please follow these steps to try it
out.

* Download and install the prerequisites
  * [Blender](http://www.blender.org/) 2.80 or later. The plugin is known to run with [Blender 2.82](http://www.blender.org/features/past-releases/2-82/).
  * Laubwerk Python3 SDK 1.0.32 or later, provided by all Laubwerk Plant Kits, including the [Plants Kit Freebie](http://www.laubwerk.com/store/plants-kit-freebie).
* Installation options
  * Latest from GitHub
    * Exit Blender
    * Clone the `thicket` git repository into the Blender `addons` folder:
      * Mac: `~/Library/Blender/2.80/scripts/addons/thicket`
      * Windows: `%AppData%\Blender Foundation\Blender\2.80\scripts\addons\thicket`
    * Start Blender
  * From a release Zip file
    * Download the latest release zip file from the [Releases Tab](/../../releases/)
    * Start Blender
    * Choose `Edit -> Preferences -> Add-ons -> Install`
    * Select the zip file and click `Install Add-on`
* Configure Thicket
  * Choose `Edit -> Preferences...`
  * Select the `Add-ons` tab and search for `thicket`
  * Check the box to enable the row `Import: Thicket: Laubwerk Plants Add-on for
    Blender`
    * If you have more than one version installed, be sure to only enable one at
      a time
  * Click the arrow to expand the add-on preferences
  * Enter the Laubwerk install path. The box will be red until a valid path is
    entered, then the Laubwerk SDK version will be displayed below the path.
  * Click `Rebuild Database`. This will take a few minutes depending on your computer and the number of Laubwerk Plants Kits installed.
  * When it completes, the number of plants in the database is displayed
* Thicket is now ready to use (see Usage)

![doc/thicket-prefs-half.png](doc/thicket-prefs-half.png)

## Usage
Thicket will eventually present a searchable plat library using thumbnail images. Until then, you can import plant models using `File -> Import -> Laubwerk Plant (.lbw.gz)`.

![doc/thicket-import-menu-full-half.png](doc/thicket-import-menu-full-half.png)

The file dialog will default to the Laubwerk Plants installation path, presenting you with a listing of plant names as directories. Open a plant directory, and select the similarly named lbw.gz file, such as `Acer_palmatum.lbw.gz`.

![doc/thicket-filebrowser-half.png](doc/thicket-filebrowser-half.png)

The image preview will update when you change the model variant and age. You can also configure season and level of detail using the Viewport and Render settings.

Plant Model
* Model: Select variant and age. There are typically 3 variants of each plant,
  as well as 3 ages for each variant.
* Season: Affect plant's foliage, color, and flowers.

Viewport Settings
* Display Proxy: Control the model displayed in the viewport
  * True: low poly proxy (convex hull)
  * False: low detail full geometry model

Render Settings
* Subdivision: Control the number of edges in a branch cross-section (0 is square)
* Leaf Density: Control how full the foliage appears
* Leaf Amount: Control the number of leaves used to reach the specified density
  (fewer leaves results in larger individual leaves)
* Maximum Level: Limit the number of branching levels off the trunk
* Minimum Thickness: Eliminate branches smaller than this value

For example. Importing Acer Palmatum with `Display Proxy` checked, loads the
convex hull into the viewport:
![doc/thicket-import-proxy-half.png](doc/thicket-import-proxy-half.png)

Importing the same plant with `Display Proxy` unchecked loads a low detail
version of the full geometry into the viewport:
![doc/thicket-import-noproxy-half.png](doc/thicket-import-noproxy-half.png)

The rendered model would be the same for each, resulting in the following
rendered image:
![doc/thicket-import-render-half.png](doc/thicket-import-render-half.png)

## Collections and Instancing
Thicket organizes each import into a top level collection named "Thicket" which is excluded from the View Layer by default. Each plant is a collection consisting of the viewport object and the render object as a child of the viewport object. Object visibility settings specify which object is visible in the viewport, and which is visible for rendering. At import time, a Collection Instance of the plant collection is added to the main scene collection. This is the object that is visible after import.

The collection model is shown in the image below by checking the Thicket
collection and expanding the plant collection and object hierarchy:
![doc/thicket-collections-half.png](doc/thicket-collections-half.png)

The collection instance can be duplicated `Shift+D` to add a second identical plant to the scene, without doubling the memory used. Because Collection Instances are displayed in the viewport, modifying the original collection in the Thicket collection will be reflected in all the instances.

In short, leave the Thicket collection unchecked and duplicate the Collection Instance in the scene to make memory efficient copies of plants.

## Report an Issue
If you think you have found a problem or a bug with Thicket, please [Check Existing Issues](/../../issues) to see if someone has already reported it. If not, please [Create a New Issue](/../../issues/new/choose), providing as much detail as possible to help us recreate the problem.

## Contributing ##
See [CONTRIBUTING](CONTRIBUTING.md) for more information.
