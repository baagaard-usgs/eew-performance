# ======================================================================
#
#                           Brad T. Aagaard
#                        U.S. Geological Survey
#
# ======================================================================
#


import logging
import numpy

import openquake.hazardlib.gsim.base
import openquake.hazardlib.imt
import openquake.hazardlib.const

import greatcircle

# ----------------------------------------------------------------------
class OpenQuakeGMPE(object):
    """
    Ground-motion prediction equation (GMPE) interface to OpenQuake hazardlib.
    """
    FIELDS = {
        "pgaG": openquake.hazardlib.imt.PGA(),
        "pgvCmps": openquake.hazardlib.imt.PGV(),
    }
    
    def __init__(self, name):
        """
        Constructor.

        :type name: str
        :param name:
            Name for GMPE [BSSA2014, ASK2014, CB2014, CY2014]
        """
        if name == "BSSA2014":
            import openquake.hazardlib.gsim.boore_2014
            self.gmpe = openquake.hazardlib.gsim.boore_2014.BooreEtAl2014()
        elif name == "ASK2014":
            import openquake.hazardlib.gsim.abrahamson_2014
            self.gmpe = openquake.hazardlib.gsim.abrahamson_2014.AbrahamsonEtAl2014()
        elif name == "CB2014":
            import openquake.hazardlib.gsim.campbell_bozorgnia_2014
            self.gmpe = openquake.hazardlib.gsim.campbell_bozorgnia_2014.CampbellBozorgnia2014()
        elif name == "CY2014":
            import openquake.hazardlib.gsim.chiou_youngs_2014
            self.gmpe = openquake.hazardlib.gsim.chiou_youngs_2014.ChiouYoungs2014()
        else:
            raise ValueError("Unknown OpenQuake GMPE '%s'." % name)
        return

    def computeMean(self, event, points):
        """
        Compute mean PGA (g) and PGV (cm/s).

        :type event: dict
        :param event:
            Dictionary with event parameters ["magnitude", "longitude", "latitude", "depth_km"]

        :type points: dict of Numpy arrays or Numpy structured array
        :param points:
            Point locations and metadata ["longitude", "latitude", "vs30"].

        :returns: tuple
           Tuple of PGA and PGV.
        
        """
        ruptureContext = self._ruptureContext(event)
        sitesContext = self._sitesContext(points)
        distContext = self._distanceContext(event, points)

        fields = OpenQuakeGMPE.FIELDS
        
        numFields = len(fields.keys())
        numPoints = points["longitude"].shape[0]
        dtype = {
            "names": [s.encode("UTF8") for s in sorted(fields.keys())],
            "formats": ["float64"]*numFields,
        }
        data = numpy.zeros(numPoints, dtype=dtype)

        for field in fields:
            imt = self.FIELDS[field]
            (values,stddev) = self.gmpe.get_mean_and_stddevs(sitesContext, ruptureContext, distContext, imt, [openquake.hazardlib.const.StdDev.TOTAL])
            data[field] = self.gmpe.to_imt_unit_values(values)
        return data

    def _ruptureContext(self, event):
        """Set rupture parameters. 

        Assumptions:
            1. Vertical, strike-slip fault.
            2. Width from a circular rupture with a stress drop of 3.0 MPa.

        :type event: dict
        :param event:
            Dictionary with event parameters ["magnitude", "depth_km"]
        """
        STRESS_DROP = 3.0e+6 # Pa
        seismicMoment = 10**(1.5*(event["magnitude"]+10.7)-7.0)
        radiusKm = 1.0e-3 * (7.0/16.0*seismicMoment/STRESS_DROP)**(1/3.0)
        widthKm = 2.0 * numpy.minimum(event["depth_km"], radiusKm)
        
        context = openquake.hazardlib.gsim.base.RuptureContext()
        context.mag = event["magnitude"]
        context.dip = 90.0
        context.rake = 0.0
        context.ztor = numpy.maximum(0.0, event["depth_km"] - 0.5 * widthKm)
        context.hypo_depth = event["depth_km"]
        context.width = widthKm # only used in CB2014 and ASK2014 hanging wall terms
        return context

    def _sitesContext(self, points):
        """Set site parameters.

        Assumptions:
            1. Z1.0 from vs30 using relation given in ASK2014.
            2. Z2.5 from vs30 using relation given in CB2014.

        :type points: dict of Numpy arrays or Numpy structured array
        :param points:
            Point locations and metadata ["vs30"].
        """
        # Compute Z1.0 using ASK2014 reference relation (similar to CY2014)
        z1pt0Km = 1.0e-3 * numpy.exp((-7.67 / 4.) * numpy.log((points["vs30"]**4 + 610.**4) / (1360.**4 + 610.**4)))

        # Compute Z2.5 using CB2014 California equation.
        z2pt5Km = numpy.exp(7.089 - 1.144 * numpy.log(points["vs30"]))
        
        context = openquake.hazardlib.gsim.base.SitesContext()
        context.vs30 = points["vs30"]
        context.z1pt0 = z1pt0Km
        context.z2pt5 = z2pt5Km
        context.vs30measured = False*numpy.ones(points["vs30"].shape, dtype=numpy.bool)
        return context

    def _distanceContext(self, event, points):
        """Get rupture distance information using great circle path.

        Assumptions:
            1. Vertical, strike-slip fault.
            2. Rx and Ry0 = 0.0 (neglect hanging wall effects in CY2014, CB2014, ASK2014)

        :type event: dict
        :param event:
            Dictionary with event parameters ["longitude", "latitude"]

        :type points: dict of Numpy arrays or Numpy structured array
        :param points:
            Point locations and metadata ["longitude", "latitude"].
        """
        context = openquake.hazardlib.gsim.base.DistancesContext()
        distEpiKm = 1.0e-3*greatcircle.distance(event["longitude"], event["latitude"], points["longitude"], points["latitude"])        
        context.rjb = distEpiKm
        context.rrup = distEpiKm
        context.rx = numpy.zeros(distEpiKm.shape) # Neglect hanging wall effects
        context.ry0 = numpy.zeros(distEpiKm.shape) # Neglect hanging wall effects
        return context

# End of file
