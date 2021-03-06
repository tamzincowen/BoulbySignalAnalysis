import playDarts as pd
import numpy as np

UNKNOWN_FIRSTOFF = 90
KNOWN_FIRSTOFF = 180

CORE_NAMES = ['Core_1', 'Core_2']

#Class takes in a signal class as defined in DBParse.py and creates the spectrum
#For an experiment.
class ExperimentGenerator(object):
    def __init__(self,signalClass, offtime, uptime, resolution, unknown_core, totaldays):
        self.signals = signalClass.signals
        self.efficiency = signalClass.efficiency
        self.offtime = offtime
        self.uptime = uptime
        self.totaldays = totaldays
        self.resolution = resolution
        self.unknown_core = unknown_core
        self.numcycles = self.totaldays / self.resolution #Number of resolution periods measured
        self.experiment_days = np.arange(1*self.resolution,(self.numcycles+1)* \
                self.resolution, self.resolution)

        #First, populate non-reactor backgrounds
        self.avg_NRbackground = 0 #In events/resolution width
        self.NR_bkg = []     #Array with experiments' non-reactor backgrounds
        self.NR_bkg_unc = [] #Uncertainty bar width for each background entry
        self.generateNRBKG()

        #First, generate core events as if reactor cores were always on
        self.known_core_events = []
        self.known_core_binavg = 'none'
        self.unknown_core_events = []
        self.unknown_core_binavg = 'none'
        self.generateCoreEvents()
        self.events_allcoreson = self.NR_bkg + self.known_core_events + \
                self.unknown_core_events

        #Now, remove events based on days a core is off
        self.removeCoreOffEvents()
        self.events = self.NR_bkg + self.known_core_events + \
                self.unknown_core_events
        self.events_unc = np.sqrt(self.events)

    #Generates non-reactor backgrounds
    def generateNRBKG(self):
        bkg_signal_dict = {}
        avg_NRbackground = 0. #In events/day
        #Fire average events for each
        for signal in self.signals:
            if signal not in CORE_NAMES:
                avg_events = self.signals[signal]*self.resolution
                avg_NRbackground = avg_NRbackground + avg_events
                events = pd.RandShoot_p(avg_events, self.numcycles)
                bkg_signal_dict[signal] = events
        self.avg_NRbackground = avg_NRbackground
        self.NR_bkg = [] #clear out NR_bkg if already filled previously
        for bkg_signal in bkg_signal_dict:
            self.NR_bkg.append(bkg_signal_dict[bkg_signal])
        self.NR_bkg = np.sum(self.NR_bkg, axis=0)
        self.NR_bkg_unc = []
        self.NR_bkg_unc = np.sqrt(self.NR_bkg)

    #Generates core events for known core (reactor background) and unknown core
    #DOES NOT assume shut-offs occur.
    def generateCoreEvents(self):
        core_signal_dict = {}
        core_binavg_dict = {}
        for signal in self.signals:
            if signal in CORE_NAMES:
                core_binavg = self.signals[signal]*float(self.resolution)
                binned_events = pd.RandShoot_p(core_binavg, self.numcycles)
                core_signal_dict[signal] = binned_events
                core_binavg_dict[signal] = core_binavg
        for core in core_signal_dict:
            if core == self.unknown_core:
                self.unknown_core_events = core_signal_dict[core]
                self.unknown_core_binavg = core_binavg_dict[core]
            else:
                self.known_core_events = core_signal_dict[core]
                self.known_core_binavg = core_binavg_dict[core]

    def removeCoreOffEvents(self):
        '''
        Code defines the first shutoff days for each reactor.  Then,
        goes through the experiment, bin by bin, and re-shoots a value
        for each bin with the average scaled by how many days the reactor
        was off for that bin.
        '''
        #generate the days that each reactor shuts off
        core_shutoffs = {'Core_1': [], 'Core_2': []}
        for core in core_shutoffs:
            if core == self.unknown_core:
                shutoff_day = UNKNOWN_FIRSTOFF
            else:
                shutoff_day = KNOWN_FIRSTOFF
            core_shutoffs[core].append(shutoff_day)
            while ((shutoff_day + self.uptime) < (self.totaldays - self.offtime)):
                shutoff_day = (shutoff_day + self.offtime) + self.uptime
                core_shutoffs[core].append(shutoff_day)
        print("CORE SHUTOFF DAYS: " + str(core_shutoffs))        
        #Now, go through each bin of core data and remove the appropriate
        #portion of reactor flux for the shutoff

        for core in core_shutoffs:
            for shutdown_day in core_shutoffs[core]:
                OT_complete = False
                for j,daybin in enumerate(self.experiment_days):
                    flux_scaler = 1.0 #Stays 1 if no off-days in bin
                    #If a shutdown happened, scale the events according to
                    #Days on before offtime begins
                    if shutdown_day < daybin:
                        dayson_beforeOT = self.resolution - (daybin - shutdown_day)
                        if dayson_beforeOT > 0:
                            flux_scaler = (float(dayson_beforeOT) / float(self.resolution))
                        else:
                            flux_scaler = 0
                    #If a reactor started back up, add back the proper
                    #flux ratio
                    if ((shutdown_day + self.offtime) < daybin):
                            dayson_afterOT = daybin - (shutdown_day + self.offtime)
                            flux_scaler += (float(dayson_afterOT) / float(self.resolution))
                            OT_complete = True
                    #After calculating how much this bin should be scaled for
                    #This day, re-fire the bin value if re-scaled 
                    #statistics are needed
                    if flux_scaler < 1.0:
                        if core == self.unknown_core:
                            self.unknown_core_events[j] = pd.RandShoot_p((flux_scaler * self.unknown_core_binavg), 1)
                        else:
                            self.known_core_events[j] = pd.RandShoot_p( \
                                    (flux_scaler * self.known_core_binavg), 1)
                    if OT_complete:
                        break
 
    def show(self):
        print("Average Non-Reactor background events per division: " + \
                str(self.avg_NRbackground))
        print("Background array: \n" + str(self.NR_bkg))
        print("day of experiment array: \n" + str(self.experiment_days))

