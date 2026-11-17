# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


#type: ignore

import bpy

from . import preferences
from . import model_setup
from . import properties
from . import migration
from . import ui
from . import profile_operators
from . import generate_operators
from . import generated_keys
from . import segment_operators
from . import segment_draw
from . import segment_mouse

addon_modules = (
    preferences,
    model_setup,
    properties,
    migration,
    ui,
    profile_operators,
    generate_operators,
    generated_keys,
    segment_operators,
    segment_draw,
    segment_mouse,
)

def register():
    for mod in addon_modules:
        mod.register()

def unregister():
    for mod in reversed(addon_modules):
        mod.unregister()


if __name__ == "__main__":
    register()
