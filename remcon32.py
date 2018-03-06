'''
Created on Feb 5, 2015

@author: Frank Ogletree, based on earlier version of Hao Wu
Significant changes for python 3 Frank 3/15/17
Thicker wrapper, some commands left out on purpose (gun off for example)
'''
import serial
import numpy as np
import time
from _collections import OrderedDict


class Remcon32(object):
    
    #direct serial communications, Zeiss Remcon32 response parsing++++++++++++++++++++++++++++++++
    
    def __init__(self, port='COM4',debug=False):
        '''
        The serial setting has to be exact the same as the setting on the RemCon32 Console
        '''
        self.timeout = 0.50    #readline called twice, timeout only for comm errors
        self.port=port
        self.ser = serial.Serial(port=self.port, baudrate=9600, 
                                    bytesize= serial.EIGHTBITS, parity=serial.PARITY_NONE, 
                                    stopbits=serial.STOPBITS_ONE, timeout=self.timeout)
    
    def close(self):
        self.ser.close()
        
    remcon_error = {600: 'Unknown command',
                    601: 'Invalid number of parameters',
                    602: 'Invalid parameter type',
                    603: 'Parameter out of range',
                    604: 'Command timeout',
                    605: 'Catastrophic error - reboot system',
                    611: 'Unexpected external control abort',
                    613: 'Parameter Unattainable',
                    614: 'Option Not Fitted',
                    615: 'Cannot change that parameter',
                    616: 'Cannot execute that command',
                    617: 'Command exceeded the max length of chars'}
    
    def cmd_response(self,cmd,error_ok=False):
        '''
        sends bytestring terminated by \r to Remcon32 program, parses return values
        some commands like read scm return errors if the scm is off, likewise out of range arguments
            if error_ok is set, this info returned instead of throwing errors
        '''
        self.ser.reset_input_buffer()    #clear any leftover stuff
        cmd = cmd.encode('ascii') + b'\r'
        self.ser.write(cmd)

        r1 =self.ser.readline() #is '@\r\n' for success or '#\r\n' for failure
        r2 =self.ser.readline() 
        #is '>[data]\r\n' for success or '* errnum\r\n' for failure
        #[data] may be empty for set commands, returns info for get

        if ( (len(r1)<1) or (r1[0]!=ord(b'@')) or (len(r2)<1) or (r2[0]!=ord(b'>')) ):
            if error_ok:
                return r2.decode('ascii')
            elif r2[0]==ord(b'*'):
                key = int(r2[1:-2])
                return 'remcon error {} {}'.format(key, self.remcon_error[key])
            else:
                return 'remcon error, command: {} text {} {}'.format( cmd, r1, r2)        
        if len(r2) > 3:
            #return data, if any, always single line
            return r2[1:-2].decode('ascii')
        
    def limits(self, x, xmin=-100.0, xmax=100.0):
        #force value between limits, many params +- 100
        return min( xmax, max(xmin, x))

    '''
    SEM kV, EHT, blanking++++++++++++++++++++++++++++++++++++++++++++++++++
    '''
    def get_kV(self):
        #gets actual, not requested, value, may be delayed for change kV or EHT on
        return float(self.cmd_response('EHT?'))
    
    def set_kV(self,val):
        #command returns immediately, EHT may take several seconds to reach new value
        #success returns None, system does not echo command
        val = min(val, 30.0)
        return self.cmd_response('EHT %f' % val)
    
    def set_eht_state(self,state=True):
        if state:
            return self.cmd_response('bmon 1') #turns on EHT, also gun if off
        else:
            return self.cmd_response('bmon 2') #turns off EHT, gun stays on
        
    def get_eht_state(self):
        kV = self.get_kV()
        if kV > 0:
            return True
        return False

    def set_blank_state(self,state=True):
        if state:
            return self.cmd_response('bblk 1') #blanks beam
        else:
            return self.cmd_response('bblk 0') 
        
    def get_blank_state(self):
        return bool(int(self.cmd_response('bbl?')))

    '''
    Lens colunm control, aperture, stig, gun etc++++++++++++++++++++++++++++++++++++
    '''
    def set_stig(self,x_val,y_val):
        x_val = self.limits( x_val)
        y_val = self.limits( y_val)
        return self.cmd_response('stim {} {}'.format(x_val, y_val))
        
    def get_stig(self):
        resp = self.cmd_response('sti?')
        return np.fromstring(resp,sep=' ')
        
    def set_ap(self,val):
        #select aperture, fails for Auger
        val = int(self.limits(val,1,6))
        return self.cmd_response('aper %i' % val)
        
    def get_ap(self):
        #value for current selected aperture
        resp = self.cmd_response('apr?')
        return int(resp)
        
    def set_ap_xy(self,x_val,y_val):
        #value for current selected aperture'
        x_val = self.limits( x_val)
        y_val = self.limits( y_val)
        return self.cmd_response('aaln {} {}'.format(x_val, y_val))
        
    def get_ap_xy(self):
        #value for current selected aperture'
        resp = self.cmd_response('aln?')
        return np.fromstring(resp,sep=' ')
        
    def set_gun_align(self,x_val,y_val):
        #value for current selected aperture'
        x_val = self.limits( x_val)
        y_val = self.limits( y_val)
        return self.cmd_response('galn {} {}'.format(x_val, y_val))
    
    def set_beam_shift(self,x,y):
        #this command +- 1 instead of +- 100%...'
        x = self.limits(x)/100.0
        y = self.limits(y)/100.0
        return self.cmd_response('BEAM {} {}'.format(x,y))
    
    def high_current_state(self, state=True):
        #can only set with macros, not in remcon
        #not for Auger
        if state:
            self.run_macro(8)
        else:
            self.run_macro(9)
    
    def set_probe_current(self,mode):
        #only for Auger
        if mode == '3.0 nA':
            self.run_macro(5)
        elif mode == '1.0 nA':
            self.run_macro(6)
        elif mode == '400 pA':
            self.run_macro(7)
        else:
            self.run_macro(4)
           
        
#    CAN SET BUT NOT READ...
#    def get_gun_align(self):
#        'value for current selected aperture'
#        resp = self.cmd_response('gal?')
#        return np.fromstring(resp,sep=' ')
#    
    def scm_state(self,state=True):
        #specimen current monitor, when on touch alarm disabled'
        #when off, 10 v bias on sample'
        if state:
            return self.cmd_response('scm 1') 
        else:
            return self.cmd_response('scm 0') 

    def get_scm(self):
        #in amps
        #this command fails if SCM is off
        value = self.cmd_response('prb?',error_ok=False)
        try:
            current = float(value)
        except ValueError:
            current = 0.0
        return current
        


    '''
    detectors and signals++++++++++++++++++++++++++++++++++++
    '''
    def display_focus_state(self,state=True):
        #this controls which display gets/sets brightness, contrast, detector...'
        #missing from remcon, do with macros'
        if state:
            self.run_macro(2) # 'Zone = 0'
        else:
            self.run_macro(3) # 'Zone = 1'
    
    def set_contrast_primary(self,val):
        self.set_contrast_bright(val,True)
        
    def get_contrast_primary(self):
        self.get_contrast_bright(True)
        
    def set_contrast_secondary(self,val):
        self.set_contrast_bright(val,True)
        
    def get_contrast_secondary(self):
        self.get_contrast_bright(True)
        
    def set_chan_bright(self,val=50,primary=True):
        self.display_focus_state(primary)
        self.set_bright(val)
        self.display_focus_state(True) #focus on primary display
    
    def get_chan_bright(self,primary=True):
        self.display_focus_state(primary)
        b = self.get_bright()
        self.display_focus_state(True) #focus on primary display
        return b
    
    def set_chan_contrast(self,val=30,primary=True):
        self.display_focus_state(primary)
        self.set_contrast(val)
        self.display_focus_state(True) #focus on primary display
    
    def get_chan_contrast(self,primary=True):
        self.display_focus_state(primary)
        c = self.get_contrast()
        self.display_focus_state(True) #focus on primary display
        return c
    
    def set_chan_detector(self,name,primary=True):
        self.display_focus_state(primary)
        self.set_detector(name)
        self.display_focus_state(True) #focus on primary display
    
    def get_chan_detector(self,primary=True):
        self.display_focus_state(primary)
        name = self.get_detector()
        self.display_focus_state(True) #focus on primary display
        return name
    
    def dual_channel_state(self,state=True):
        if state:
            self.run_macro(1) # 'DualMonitor = On'
        else:
            self.run_macro(10)
        
    def set_bright(self,val=50):
        #this actually sets voltage offset of detector output, best 50% neutral for quantitative data'
        #for currently selected display
        val = self.limits(val,0,100)
        return self.cmd_response('bgtt %f' % val)
    
    def get_bright(self):
        return float(self.cmd_response('bgt?'))
    
    def set_contrast(self,val=50):
        #this actually sets electron multiplier gain/voltage'
        #for currently selected display'
        val = self.limits(val,0,100)
        return self.cmd_response('crst %f' % val)
    
    def get_contrast(self):
        #of active display, which cannot be set'
        return float(self.cmd_response('cst?'))

    def get_detector(self):
        #for currently selected display'
        return self.cmd_response('det?')
        
    def set_detector(self, name):
        #for currently selected display'
        return self.cmd_response('det %s' % name)
    
    def set_norm(self):
        #makes scanning "normal" ie both unfrozen, non spot'
        return self.cmd_response('norm')
    
    def run_macro(self,n):
        '''
        runs macro REMCONn in SmartSem, macro must exist or error'
        fill in for missing commands
        
        REMCON1 sets dual monitor mode ON
        REMCON2 display focus primary
        REMCON3 display focus secondary
        REMCON4 - Auger, set probe current Max
        REMCON5 - Auger, set probe current 3.0 nA
        REMCON6 - Auger, set probe current 1.0 nA
        REMCON7 - Auger, set probe current 400 pA
        REMCON8 - Except Auger, high current ON
        REMCON9 - Except Auger, high current OFF
        REMCON10 - set dual monitor OFF
        
        also SmartSem START macro runs Remcon32 in autoconnect mode
        '''
        return self.cmd_response('mac %i' % n)
   
        
    '''
    imaging++++++++++++++++++++++++++++++++++++++++++
    '''   
   
    def set_extscan_state(self,state=True):
        if state:
            return self.cmd_response('edx 1') #ext scan
        else:
            return self.cmd_response('edx 0') 
        
    def get_extscan_state(self):
        return bool(int(self.cmd_response('exs?')))
   
    def set_mag(self,val=500):
        val = self.limits(val,5,1e6)
        return self.cmd_response('mag %f' % val)
    
    def get_mag(self):
        return float(self.cmd_response('mag?'))
   
    def set_wd(self,val=9.2):
        #in mm, max depends on voltage where obj lens current goes to zero
        val = self.limits(val,0.0,50.0)
        return self.cmd_response('focs %f' % val)
    
    def get_wd(self):
        return float(self.cmd_response('foc?'))
   
    def get_pixel_size(self):
        #width of image / 1024, regardless of actual resolution, returned in nm and converted to SI
        return 1e-9*float(self.cmd_response('pix?'))
   
    def set_spot_mode(self,x_val,y_val):
        x_val = int(self.limits(x_val,0,1023))
        y_val = int(self.limits(y_val,0,767))
        return self.cmd_response('spot {} {}'.format(x_val, y_val))
    
    '''
    stage control (not for Auger)+++++++++++++++++++++++++++++++++++++++++++++
    '''
       
    def get_stage_position(self):
        'returns x y z tilt rot M status'
        'for 5/6 axis stage, last param is 1.0 in motion, 0.0 done'
        resp = self.cmd_response('c95?')
        return np.fromstring(resp,sep=' ', dtype=float) #array of 7 floats
    
    def get_stage_initialized_state(self):
        'returns stage type (int) and is_initialized (int, 0 = initialized, 1 = NOT)'
        resp = self.cmd_response('ist?')
        status = np.fromstring(resp,sep=' ', dtype=int)
        if status[1]:
            return False
        else:
            return True
        
    def get_stage_position_dict(self):
        pos_array = self.get_stage_position()
        names = ['x', 'y', 'z', 'tilt', 'rot', 'M', 'status']
        return OrderedDict(zip(names, pos_array))

    def set_stage_position(self, x, y, z, tilt, rot ):
        'error if out of physical limits, can be dangerous'
        state = self.get_scm()
        self.scm_state(False)   #turn off scm so touch alarm works!
        cmd = 'c95 {} {} {} {} {} 0.0'.format(x,y,z,tilt,rot)
        resp = self.cmd_response(cmd)
        if type(resp) is float:
            self.scm_state(True) #restore scm if it returned a numerical value (else error string)
        return resp
        
        
     
