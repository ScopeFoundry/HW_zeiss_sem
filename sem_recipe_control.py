'''
    Manage stored SEM image conditions
    Act as SEM Control panel
    
    Some items 
'''
from ScopeFoundry import Measurement
from collections import OrderedDict
import csv
import time
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import configparser

### on init

# read csv file, populate data structure, populate dynamic list of recipes, maybe append (xx days old)

# items: name, date, kV, WD, aperture (CL), high_current (CL), beam_current (Auger), stig_xy, app_xy, gun_xy (Auger)
# items with CL or Auger after are only set in the corresponding modes

'''
remcon enabled when measurement starts
contrast is controlled, brightness set to 50% both detectors

for the auger version the list can be beam currents instead of apertures
for the standard versions the gun_xy controls can be disabled.

delete removes entry from list and csv file

update saves new values to csv and updates date

new creates entry using value in text box


'''



class SEMRecipeControlMeasure(Measurement):
    
    name = 'sem_recipe_control'

    recipe_remcon_settings = ["kV", "WD", "high_current", "select_aperture",
                              "stig_x", "stig_y", "aperture_x", "aperture_y", "gun_x", "gun_y"]
    
    def setup(self):

        hw = self.remcon_hw = self.app.hardware['sem_remcon']
        
        self.settings.New('recipes_filename', dtype='file', initial='')
        self.settings.New('recipe_name', dtype=str, initial='recipe1', choices=('recipe1', ))
        for setting_name in self.recipe_remcon_settings:
            hw_lq = hw.settings.get_lq(setting_name)
            self.settings.New('recipe_' + setting_name,
                              dtype=hw_lq.dtype,
                              unit=hw_lq.unit,
                              choices=hw_lq.choices,
                              ro=True)
            
        self.settings.New('recipe_date_modified', dtype=str, ro=True)
        
        
        # list of recipe dicts
        self.recipes = []
                

    def setup_figure(self):
        
        self.ui = load_qt_ui_file(sibling_path(__file__, 'sem_recipe_control.ui'))
        
        self.settings.recipes_filename.connect_to_browse_widgets(
            self.ui.recipes_filename_lineEdit,
            self.ui.recipes_filename_browse_pushButton)
        
        widget_names = [
            ('kV', 'kV_doubleSpinBox'),
            ('WD', 'WD_doubleSpinBox'),
            ('aperture_x', 'aperture_x_doubleSpinBox'),
            ('aperture_y', 'aperture_y_doubleSpinBox'),
            ('stig_x', 'stig_x_doubleSpinBox'),
            ('stig_y', 'stig_y_doubleSpinBox'),
            ('gun_x', 'gun_x_doubleSpinBox'),
            ('gun_y', 'gun_y_doubleSpinBox'),
            ('select_aperture', 'select_aperture_comboBox'),
            ('high_current', 'high_current_checkBox')
        ]

        # Current REMCON conditions        
        for lq_name, widget_name in widget_names:
            hw_lq = self.remcon_hw.settings.get_lq(lq_name)
            widget = getattr(self.ui, widget_name)
            hw_lq.connect_to_widget(widget)
            
        self.remcon_hw.settings.magnification.connect_to_widget(
            self.ui.mag_doubleSpinBox)
        self.remcon_hw.settings.contrast0.connect_to_widget(
            self.ui.contrast_doubleSpinBox)
        #self.remcon_hw.settings.rot.connect_to_widget(
        #    self.ui.rotation_doubleSpinBox)
        self.remcon_hw.settings.beam_blanking.connect_to_widget(
            self.ui.beam_blank_checkBox)
        self.remcon_hw.settings.eht_on.connect_to_widget(
            self.ui.eht_checkBox)
        
        self.remcon_hw.connected.connect_to_widget(self.ui.hw_connect_checkBox)
        self.ui.read_sem_pushButton.clicked.connect(self.remcon_hw.read_from_hardware)
        

        # Recipe conditions
        for lq_name, widget_name in widget_names:
            print("---",lq_name)
            lq = self.settings.get_lq("recipe_" + lq_name)
            widget = getattr(self.ui, "recipe_" + widget_name)
            lq.connect_to_widget(widget)
      
        self.settings.recipe_date_modified.connect_to_widget(self.ui.recipe_date_modified_label)

        self.ui.save_recipe_pushButton.clicked.connect(self.on_save_recipe)
        self.ui.execute_pushButton.clicked.connect(self.execute_current_recipe)
        self.ui.delete_recipe_pushButton.clicked.connect(self.delete_current_recipe)
        
        self.settings.recipe_name.connect_to_widget(self.ui.recipe_name_comboBox)
        self.settings.recipe_name.add_listener(self.select_current_recipe)
        
        
        self.settings.recipes_filename.add_listener(self.load_recipes_file)
        
        self.settings['recipes_filename'] = 'sem_recipes_default.ini'


    def get_recipe_by_name(self, name):
        for recipe in self.recipes:
            if recipe['name'] == name:
                return recipe
        raise ValueError("recipe not found {}".format(name))
        
    
    def load_recipes_file(self):
        
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(self.settings['recipes_filename'])

        self.recipes.clear()
        for name in config.sections():
            recipe_dict = OrderedDict()
            recipe_dict['name'] = name
            for key, val in config.items(name):
                recipe_dict[key] = val
            self.recipes.append(recipe_dict)
    
        # update recipe choices
        self.settings.recipe_name.change_choice_list(tuple([r['name'] for r in self.recipes]))
        
        # set recipe_name to first record if current recipe_name is not in file
        current_recipe_name = self.settings['recipe_name']
        if current_recipe_name in self.recipes:
            self.select_current_recipe(current_recipe_name)
        else:
            self.settings['recipe_name'] = self.recipes[0]['name']
    
    
    def save_recipes_file(self):
#         with open(self.settings['recipes_filename'], 'w', newline="") as recipes_file:
#             writer = csv.writer(recipes_file)
#             header = list(self.recipes[0].keys())
#             writer.writerow(header)
#             for recipe in self.recipes:
#                 writer.writerow( [ recipe[column] for column in header ] )
        config = configparser.ConfigParser()
        config.optionxform = str
        
        for recipe in self.recipes:
            config.add_section(recipe['name'])
            for setting_name in (self.recipe_remcon_settings + ['date_modified',]):
                print(recipe['name'], setting_name, recipe[setting_name])
                config.set(recipe['name'], setting_name, str(recipe[setting_name]))
    
        with open(self.settings['recipes_filename'], 'w') as configfile:
            config.write(configfile)
    
    def select_current_recipe(self, name=None):
        print("select_current_recipe", name)
        if name is None:
            name = self.settings['recipe_name']
        print("select_current_recipe", name)
        recipe = self.get_recipe_by_name(name)
        
        self.ui.new_recipe_name_lineEdit.setText(name)       
        # update recipe logged quantities
        for setting_name in self.recipe_remcon_settings:
            self.settings['recipe_' + setting_name] = recipe[setting_name]
            
        self.settings['recipe_date_modified'] = recipe['date_modified']
    
    
    def delete_current_recipe(self):
        recipe = self.get_recipe_by_name(self.settings['recipe_name'])        
        self.recipes.remove(recipe) 
        self.save_recipes_file()
        self.load_recipes_file()
    
    
    def save_current_settings_as_recipe(self, name):
        new_recipe = OrderedDict()
        new_recipe['name'] = name
        for setting_name in self.recipe_remcon_settings:
            new_recipe[setting_name] = self.remcon_hw.settings[setting_name]
        new_recipe['date_modified'] = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time()))
        
        try:
            old_recipe = self.get_recipe_by_name(name)
            if old_recipe['date_modified'] == 'SYSTEM':
                self.load_recipes_file()
                self.settings['recipe_name'] = name

                return
            old_recipe.update(new_recipe)
        except ValueError:
            self.recipes.append(new_recipe)

        self.save_recipes_file()
        self.load_recipes_file()
        self.settings['recipe_name'] = name
        
    
    def execute_current_recipe(self):
        # save first?
        # ask first?
        for setting_name in self.recipe_remcon_settings:
            self.remcon_hw.settings[setting_name] = self.settings['recipe_'+setting_name]

    
    
    def on_save_recipe(self):
        new_name = self.ui.new_recipe_name_lineEdit.text()
        self.save_current_settings_as_recipe(new_name)
        
        
    