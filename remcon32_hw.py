'''
Created on Feb 4, 2015

@author: Hao Wu, modified by Frank Ogletree 

Revised by Alan Buckley
'''

'remote control of Zeiss Gemini SEM using the Remcon32 serial interface'

from ScopeFoundry import HardwareComponent
from .remcon32 import Remcon32
import configparser



class SEM_Remcon_HW(HardwareComponent):
    ''' Auger system uses a different subset of commands from standard Zeiss Gemini'''
    
    name = 'sem_remcon'
    
     
    def setup(self):
        self.debug=False

        #create logged quantities
        #+- 10 V dac output moves within "full_size" box determined by mag, calculate mag with pixel size
        self.settings.New('port', dtype=str, initial='COM4')
        
        self.settings.New(
            'SEM_mode',dtype=str,initial='default',ro=True)
        self.settings.New(
            'eht_on', dtype=bool, initial=False)         
        self.settings.New(
            'external_scan', dtype=bool, initial=True )        
        self.settings.New(
            'beam_blanking', dtype=bool, initial=False )        
        self.settings.New(
            'kV', dtype=float, initial=3.0, unit='kV', vmin=0, vmax = 30.0)
        self.WD = self.settings.New(
            'WD', dtype=float, vmin=0.0, fmt='%4.3f',initial=9.3,unit='mm')        
        self.settings.New(
            'full_size', dtype=float, initial=100e-6, unit = 'm', si=True, vmin=1e-9, vmax=3e-3)
        self.settings.New(
            'magnification', dtype=float, vmin=5.0, vmax=1.0e6, si=True, unit='x')               
        self.settings.New(
            'scm_state', dtype=bool, description='Specimen Current Monitor On/Off')
        self.settings.New(
            'scm_current', dtype=float,ro=True, si=True, unit='A')        
        self.settings.New(
            'dual_channel', dtype=bool, initial=True )        
        self.settings.New(
            'high_current', dtype=bool, initial=False ) #not for Auger       
        self.settings.New(
            'contrast0', dtype=float, unit=r'%', fmt='%.1f' ,vmin=0, vmax=100, initial=30)
        self.settings.New(
            'contrast1', dtype=float, unit=r'%', vmin=0, fmt='%.1f', vmax=100,initial=30)
        self.settings.New(
            'detector0',dtype=str,initial='SE2',choices=('SE2','VPSE','InLens'))
        self.settings.New(
            'detector1', dtype=str, initial='SE2', choices=('SE2','VPSE','InLens'))       
        self.settings.New(
            'stig_xy', dtype=float, array=True, fmt='%1.1f', initial=[0,0], vmin=-100, vmax=100, unit=r'%')
        self.settings.New(
            'stig_x', dtype=float, unit=r'%')
        self.settings.New(
            'stig_y', dtype=float, unit=r'%')        
        self.settings.stig_xy.connect_element_follower_lq(self.settings.stig_x, 0)
        self.settings.stig_xy.connect_element_follower_lq(self.settings.stig_y, 1)
        # THIS IS CRITICALY IMPORTANT, do NOT remove again. Frank Oct 10, 2017
        # Since it can't be read, it's not very useful
        self.settings.New(
            'gun_xy', dtype=float, array=True, fmt='%1.1f', initial=[0,0], vmin=-100, vmax=100, unit=r'%')
        self.settings.New(
            'gun_x', dtype=float, unit=r'%')
        self.settings.New(
            'gun_y', dtype=float, unit=r'%')
        self.settings.gun_xy.connect_element_follower_lq(self.settings.gun_x, 0)
        self.settings.gun_xy.connect_element_follower_lq(self.settings.gun_y, 1)
        self.settings.New(
            'aperture_xy', dtype=float, array=True, fmt='%1.1f', initial=[0,0], vmin=-100, vmax=100, unit=r'%')
        self.settings.New(
            'aperture_x', dtype=float, unit=r'%')
        self.settings.New(
            'aperture_y', dtype=float, unit=r'%')
        self.settings.aperture_xy.connect_element_follower_lq(self.settings.aperture_x, 0)
        self.settings.aperture_xy.connect_element_follower_lq(self.settings.aperture_y, 1)
        
        # Since beamshift can't be read, give option to control or not
        self.settings.New(
            'control_beamshift', dtype=bool, initial=False)        
        self.settings.New(
            'beamshift_xy', dtype=float, array=True, fmt='%1.1f', initial=[0,0], vmin=-100, vmax=100, unit=r'%')
        
        aperture_choices=list([('[1] 30.00 μm',1),
                               ('[2] 10.00 μm',2),
                               ('[3] 20.00 μm',3),
                               ('[4] 60.00 μm',4),
                               ('[5] 120.00 μm',5),
                               ('[6] 300.00 μm',6)])
           
        self.select_aperture = self.settings.New( #not for Auger
            'select_aperture', dtype=int,ro=False, vmin=1, vmax=6, choices=aperture_choices)
        

        self.settings.control_beamshift.add_listener(self.on_change_control_beamshift)
        self.settings.magnification.add_listener(self.on_new_mag)
        self.settings.full_size.add_listener(self.on_new_full_size)

        # stage position: [x y z tilt rot M status]
        self.settings.New('stage_position',
                          dtype=float, array=True, ro = True, fmt='%1.3f', initial=[0,0,0,0,0,0,0] )

        
        self.settings.New('stage_x', dtype=float, ro=True)
        self.settings.stage_x.connect_lq_math( (self.settings.stage_position,), lambda pos: pos[0])
        
        self.settings.New('stage_y', dtype=float, ro=True)
        self.settings.stage_x.connect_lq_math( (self.settings.stage_position,), lambda pos: pos[1])
        
        self.settings.New('stage_z', dtype=float, ro=True)
        self.settings.stage_x.connect_lq_math( (self.settings.stage_position,), lambda pos: pos[2])

        self.settings.New('stage_tilt', dtype=float, ro=True)
        self.settings.stage_x.connect_lq_math( (self.settings.stage_position,), lambda pos: pos[3])

        self.settings.New('stage_rot', dtype=float, ro=True)
        self.settings.stage_x.connect_lq_math( (self.settings.stage_position,), lambda pos: pos[4])

        self.settings.New('stage_M', dtype=float, ro=True)
        self.settings.stage_x.connect_lq_math( (self.settings.stage_position,), lambda pos: pos[5])

        self.settings.New('stage_is_moving', dtype=bool, ro=True)
        self.settings.stage_x.connect_lq_math( (self.settings.stage_position,), lambda pos: bool(pos[6]))

        self.settings.New('stage_initialized', dtype=bool, ro=True)
        
        self.running_on_new_full_size = False
    
    def on_change_control_beamshift(self):
        print('control beamshift',self.settings['control_beamshift'])
        if self.settings['control_beamshift']:
            self.settings.beamshift_xy.connect_to_hardware(
                write_func=lambda XY: self.remcon.set_beam_shift(*XY)
                )
        else:
            self.settings.beamshift_xy.disconnect_from_hardware()      
    
    def on_new_mag(self):
        if hasattr(self, 'remcon') and not self.running_on_new_full_size:            
            self.settings.full_size.update_value(1024 * self.remcon.get_pixel_size())
        
    def on_new_full_size(self):
        if hasattr(self, 'remcon'):
            # SEM pixel size is always image_width / 1024, regardless of actual resolution
            old_mag = self.settings['magnification']
            old_pixel = self.remcon.get_pixel_size()
            scale_factor = old_mag*(1024*old_pixel)
            print(scale_factor)
            new_mag = scale_factor/self.settings['full_size']
            self.running_on_new_full_size = True
            self.settings.magnification.update_value(new_mag)
            self.running_on_new_full_size = False
            
                   
    def connect(self, write_to_hardware=True):
        S = self.settings
        R = self.remcon = Remcon32(port=S['port'])  
                      
        #connect logged quantity
        S.magnification.connect_to_hardware(
                read_func = R.get_mag,
                write_func = R.set_mag
                )        
        S.eht_on.connect_to_hardware(
                read_func = R.get_eht_state,
                write_func = R.set_eht_state
                )                
        S.beam_blanking.connect_to_hardware(
                read_func = R.get_blank_state,
                write_func = R.set_blank_state
                )                
        S.dual_channel.connect_to_hardware(
                write_func = R.dual_channel_state,
                )                
        S.high_current.connect_to_hardware(
                write_func = R.high_current_state,
                )                
        S.stig_xy.connect_to_hardware(
            read_func=R.get_stig,
            write_func=lambda XY: R.set_stig(*XY),
            )        
        S.gun_xy.connect_to_hardware(
            write_func=lambda XY: R.set_gun_align(*XY),
            )        
        S.aperture_xy.connect_to_hardware(
            read_func=R.get_ap_xy,
            write_func=lambda XY: R.set_ap_xy(*XY),
            )        
        S.beamshift_xy.connect_to_hardware(
             write_func=lambda XY: R.set_beam_shift(*XY)
             )        
        S.WD.connect_to_hardware(
                read_func = R.get_wd,
                write_func = R.set_wd
                )                
        S.select_aperture.connect_to_hardware(
                read_func = R.get_ap,
                write_func = R.set_ap
                )        
        S.external_scan.connect_to_hardware(
                read_func = R.get_extscan_state,
                write_func = R.set_extscan_state
                )
        S.eht_on.connect_to_hardware(
                read_func = R.get_eht_state,
                write_func = R.set_eht_state
                )
        S.stage_position.connect_to_hardware(
                read_func = R.get_stage_position,
                )
        S.stage_initialized.connect_to_hardware(
                read_func = R.get_stage_initialized_state,
                ) 
         
        S.detector0.connect_to_hardware(
                read_func = lambda: R.get_chan_detector(True),
                write_func = lambda X: R.set_chan_detector(X,True)
                )        
        S.detector1.connect_to_hardware(
                read_func = lambda: R.get_chan_detector(False),
                write_func = lambda X: R.set_chan_detector(X,False)
                )        
        S.kV.connect_to_hardware(
            read_func = R.get_kV,
            write_func = R.set_kV)       
        S.scm_state.connect_to_hardware(
            write_func=R.scm_state
            )
        S.scm_current.connect_to_hardware(
            read_func=R.get_scm
            )
        S.contrast0.connect_to_hardware(
            read_func=lambda: R.get_chan_contrast(True),                  
            write_func=lambda X: R.set_chan_contrast(X,True),            
            )
        S.contrast1.connect_to_hardware(
            read_func=lambda: R.get_chan_contrast(False),                  
            write_func=lambda X: R.set_chan_contrast(X,False),            
            )
       
        # write state to hardware
#         if write_to_hardware:
#             for lq in self.settings.as_list(): 
#                 lq.write_to_hardware()
#                 #set detector offset to zero so analog data is quantitative
        R.set_chan_bright(50,True)
        R.set_chan_bright(50,False)
        self.read_from_hardware()
        
        self.SEM_load_ini() #get stored settings list
            
    def disconnect(self):
        self.settings.disconnect_all_from_hardware()
        if hasattr(self, 'remcon'):
            self.remcon.close()
            del self.remcon
            
    def SEM_load_ini(self, fname='SEM_saved_settings.ini'):
        self.log.info("ini settings loading from " + fname)
        

        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(fname)
        print( config.sections() )
        

#         if 'app' in config.sections():
#             for lqname, new_val in config.items('app'):
#                 #print(lqname)
#                 lq = self.settings.as_dict().get(lqname)
#                 if lq:
#                     if lq.dtype == bool:
#                         new_val = str2bool(new_val)
#                     lq.update_value(new_val)

  
            
class Auger_Remcon_HW(SEM_Remcon_HW):
    '''subclass SEM_Remcon_HW to handle Auger-specific command set'''
    
        
    def setup(self):
        SEM_Remcon_HW.setup(self)
        self.settings.New('probe_current', dtype=str, 
                          initial='Max',
                          choices=('Max','3.0 nA','1.0 nA','400 pA'))
        
        self.settings['SEM_mode'] = 'Auger'
       
    def connect(self):
        SEM_Remcon_HW.connect(self, write_to_hardware=False)
        S = self.settings
        
        S.select_aperture.disconnect_from_hardware(dis_read=False)
        S.high_current.disconnect_from_hardware()
        S.stage_position.disconnect_from_hardware()
        S.select_aperture.change_readonly(True)
        S.high_current.change_readonly(True)
                
        self.settings.probe_current.connect_to_hardware(
                write_func = self.remcon.set_probe_current
                )
        
        for lq in self.settings.as_list(): 
                lq.write_to_hardware()

    
    def disconnect(self):
        SEM_Remcon_HW.disconnect(self)

