from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
import time

class SEMStageDeltaControl(Measurement):
    
    name = 'sem_stage_delta'
    insert = {'x':90.0,'y':65.0,'z':40.0,'rot':275.0} # wafer on waffle has z~=45.25mm at CL focus
    
    def setup(self):
        
        self.ui_filename = sibling_path(__file__, 'stage_delta_control.ui')
        self.ui = load_qt_ui_file(self.ui_filename)


        self.settings.New("xy_step", dtype=str, initial='10um', choices=('1um', '10um', '100um', '1mm', '10mm'))
        self.settings.New("z_step",  dtype=str, initial='10um', choices=('0.1um','1um', '10um', '100um', '1mm'))        
        self.settings.New("rot_step",  dtype=str, initial='1.0_deg', choices=('0.1_deg', '1.0_deg', '10_deg'))

        for ax in ['x', 'y', 'z', 'rot']:
            for direction in ['up', 'down']:
                button = getattr(self.ui, "{}_{}_pushButton".format(ax, direction))
                button.released.connect(lambda ax=ax, direction=direction: self.step_axis(ax, direction))


        self.remcon = self.app.hardware['sem_remcon']
        
        for ax in ['x', 'y', 'z', 'rot']:
            widget = getattr(self.ui, ax + "_pos_doubleSpinBox")
            lq = self.remcon.settings.get_lq("stage_" + ax)
            lq.connect_to_widget(widget)
            
        self.ui.read_current_pos_pushButton.clicked.connect(self.remcon.settings.stage_position.read_from_hardware)
        
        self.settings.xy_step.connect_to_widget(self.ui.step_xy_comboBox)
        self.settings.z_step.connect_to_widget(self.ui.step_z_comboBox)
        self.settings.rot_step.connect_to_widget(self.ui.step_rot_comboBox)
        
        self.remcon.settings.stage_is_moving.connect_to_widget(self.ui.is_moving_checkBox)
        self.remcon.settings.stage_initialized.connect_to_widget(self.ui.initialized_checkBox)
        self.remcon.settings.connected.connect_to_widget(self.ui.connected_checkBox)
        
        
        self.ui.move_to_insert_pushButton.clicked.connect(self.move_to_insert_position)

            
    def step_axis(self, ax, direction):
        print('step_axis', ax)
        if ax in 'xy':
            self.step_xy(ax, direction)
        elif ax == 'z':
            self.step_z(direction)
        elif ax == 'rot':
            self.step_rotation(direction)
        else:
            raise ValueError("unknown axis")



    def step_xy(self, ax, direction):
        
        step = self.settings['xy_step']
        
        int_dir = {'up':+1, 'down':-1}[direction]

        mm_step = {'1um':1e-3 , '10um': 10e-3, '100um': 100e-3, '1mm':1.0, '10mm':10.0}[step]

        # safety logic here
        if mm_step >  0.1:
            # check Z
                
            pass
                

        # Initiate move
        if ax == 'x':
            self.remcon.remcon.set_stage_delta(x=int_dir*mm_step)
        if ax == 'y':
            self.remcon.remcon.set_stage_delta(y=int_dir*mm_step)
            
        # wait until move is complete
        self.wait_until_move_complete()
        # read new position
        self.remcon.settings.stage_position.read_from_hardware()
        
    def step_z(self, direction):
        print("step_z")
        #return

        step = self.settings['z_step']
        
        int_dir = {'up':+1, 'down':-1}[direction]
    
        mm_step = {'0.1um':0.1e-3, '1um':1e-3 , '10um': 10e-3, '100um': 100e-3, '1mm':1.0}[step]

        # safety logic here
        
        self.remcon.remcon.set_stage_delta(z=int_dir*mm_step)
        
        # wait until move is complete
        self.wait_until_move_complete()
        # read new position
        self.remcon.settings.stage_position.read_from_hardware()
        
    def step_rotation(self, direction):
        
        step = self.settings['rot_step']
        
        int_dir = {'up':+1, 'down':-1}[direction]

        deg_step = {'0.1_deg':0.1 , '1.0_deg': 1.0, '10_deg': 10.0}[step]
        
        # safety logic here
        
        self.remcon.remcon.set_stage_delta(rot = int_dir*deg_step)
        
        # wait until move is complete
        self.wait_until_move_complete()
        # read new position        
        self.remcon.settings.stage_position.read_from_hardware()


    def wait_until_move_complete(self,timeout=5.0):
        import time
        t0 = time.time()
        while True:
            self.app.qtapp.processEvents()
            time.sleep(0.01)
            if time.time() - t0 > timeout:
                print("sem stage timeout occurred")
                break
            self.remcon.settings.stage_position.read_from_hardware()
            #if not self.remcon.remcon.get_stage_moving():
            #    print("done moving")
            #    break
            if not self.remcon.settings['stage_is_moving']:
                print("done moving")
                break
        time.sleep(0.01)
        self.remcon.settings.stage_position.read_from_hardware()


    
    def move_to_insert_position(self):
        # x=90, y=65, z=42, rot=275 # reference sample = self.insert dict
        
        print("move_to_insert_position")
        self.remcon.settings.stage_position.read_from_hardware()
        z = self.remcon.settings['stage_z']


        # drop z if too close
        if z > self.insert['z']:
            print("move_to_insert_position: dropping z")

            self.remcon.remcon.set_stage_position_kwargs(z=self.insert['z'])
            self.wait_until_move_complete(timeout=30.0)

        # move to insert position
        print("move_to_insert_position: initiate move")
        
        rot_targets = self.remcon.remcon.check_rotation_fault(self.remcon.settings['stage_rot'], self.insert['rot'])
        for rot_pos in rot_targets:
            I = self.insert
            self.remcon.remcon.set_stage_position_kwargs(x=I['x'], y=I['y'], z=I['z'], rot=rot_pos)
            self.wait_until_move_complete(timeout=30.0)
        
        # verify position
        print("move_to_insert_position: move done")
        self.remcon.settings.stage_position.read_from_hardware()
        
            