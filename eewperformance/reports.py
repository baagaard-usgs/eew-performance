# ======================================================================
#
#                           Brad T. Aagaard
#                        U.S. Geological Survey
#
# ======================================================================
#

import os
import datetime
import dateutil.parser
import numpy

from PIL import Image

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Table
from reportlab.lib.utils import ImageReader

from .analysisdb import AnalysisData
from .analysis_utils import analysis_event_label, timedelta_to_seconds

class AnalysisSummary(object):
    """Summary of analysis.
    """
    HEADER = 0.5*inch
    MARGIN = 0.5*inch
    PAGE_WIDTH, PAGE_HEIGHT = landscape(letter)
    MAP_SIZE = 3.25*inch
    SPACING = 0.125*inch
    
    def __init__(self, config):
        """Constructor.
        """
        self.config = config
        self.canvas = None
        return

    def generate(self, eqIds):
        """Generate report.
        """
        filename = self.config.get("files", "report")
        self.canvas = canvas.Canvas(
            filename,
            pagesize=landscape(letter),
            bottomup=1,
        )

        # Title page with damage/action figure

        for eqId in eqIds:
            self._render_event(eqId)

        self.canvas.save()
        return

    def _render_event(self, eqId):
        """Generate summary for event.
        """
        db = AnalysisData(self.config.get("files", "analysis_db"))
        event = db.comcat_event(eqId)
        shakemap = db.comcat_shakemap(eqId)
        
        # Get alerts
        server = self.config.get("shakealert.production", "server")
        alerts = db.alerts(eqId, server)
        
        # Get performance information
        #comcat_id, eew_server, gmpe, fragility, magnitude_threshold
        gmpe = self.config.get("mmi_predicted", "gmpe")
        fragility = self.config.get("fragility_curves", "object").split(".")[-1]
        perfEEW = numpy.array(db.performance_stats(eqId, server, gmpe, fragility))
        perfTheoryMag = numpy.array(db.performance_stats(eqId, "catalog-magnitude", gmpe, fragility))
        perfTheoryMagBias = numpy.array(db.performance_stats(eqId, "catalog-magnitude-bias", gmpe, fragility))

        # Page 1
        self._render_event_header(event)
        self._render_event_info(event, shakemap, alerts)
        self._render_event_perf_table(perfEEW, perfTheoryMag, perfTheoryMagBias)
        self.canvas.showPage()

        # Page 2
        self._render_event_header(event)
        self._render_event_mmi_maps(event)
        self._render_event_alert_maps(event, server)
        self.canvas.showPage()

        # Page 3
        self._render_event_header(event)
        self._render_event_mmi_correlation(event)
        self._render_event_mmi_warningtime(event)
        self._render_event_error(event)
        self.canvas.showPage()

        return

    def _render_event_header(self, event):
        ot = dateutil.parser.parse(event["origin_time"])
        fragilityFn = self.config.get("fragility_curves", "object").split(".")[-1]
        magThreshold = self.config.getfloat("alerts", "magnitude_threshold")
        mmiThreshold = self.config.getfloat("alerts", "mmi_threshold")
        header = (
            "{ot:%Y-%m-%d %H:%M:%S} {event[event_id]:s} M{event[magnitude]:.1f} {event[description]:s}".format(ot=ot, event=event),
            "Damage/Action: {fn}, Alert thresholds: M{mag:.1f}, MMI {mmi:.1f}".format(fn=fragilityFn, mag=magThreshold, mmi=mmiThreshold),
        )
        self.canvas.saveState()
        self.canvas.translate(self.MARGIN, self.PAGE_HEIGHT-self.MARGIN)
        text = self.canvas.beginText()
        text.setFont("Helvetica-Bold", 12)
        text.textLines("\n".join(header))
        self.canvas.drawText(text)
        self.canvas.restoreState()

        header = (
            "Brad Aagaard",
            "Version " + datetime.datetime.now().strftime("%Y-%m-%d %I:%M%p"),
        )
        self.canvas.saveState()
        self.canvas.translate(self.PAGE_WIDTH-self.MARGIN, self.PAGE_HEIGHT-self.MARGIN)
        self.canvas.setFont("Helvetica", 8)
        self.canvas.drawRightString(0, 0, header[0])
        self.canvas.drawRightString(0, -10, header[1])
        self.canvas.restoreState()
        return

    def _render_event_mmi_maps(self, event):
        """Maps of MMI observed, predicted, and residual (observed-predicted).
        """
        x = self.MARGIN
        y = self.PAGE_HEIGHT-(self.MARGIN+self.HEADER)-self.MAP_SIZE

        plots_dir = self.config.get("files", "plots_dir")
        label = analysis_event_label(self.config, event["event_id"])

        filename = os.path.join(plots_dir, label+"-map_mmi_obs.jpg")
        self._render_image(filename, x, y, width=self.MAP_SIZE)
    
        x += self.MAP_SIZE + self.SPACING
        filename = os.path.join(plots_dir, label+"-map_mmi_pred.jpg")
        self._render_image(filename, x, y, width=self.MAP_SIZE)

        x += self.MAP_SIZE + self.SPACING
        filename = os.path.join(plots_dir, label+"-map_mmi_residual.jpg")
        self._render_image(filename, x, y, width=self.MAP_SIZE)

        return

    def _render_event_alert_maps(self, event, server):
        """Maps of alert categories w/warning time for EEW and
        theoretical with catalog magnitude and theoretical with catalog
        magnitude with event bias.
        """
        x = self.MARGIN
        y = self.MARGIN

        plots_dir = self.config.get("files", "plots_dir")
        label = analysis_event_label(self.config, event["event_id"])

        filename = os.path.join(plots_dir, label+"-map_cost_savings.jpg")
        imageWidth, imageHeight = self._render_image(filename, x, y, width=self.MAP_SIZE)
        self._figure_label(x, y+imageHeight, "ShakeAlert")
        
        x += self.MAP_SIZE + self.SPACING
        filenameMag = filename.replace(server, "catalog-magnitude")
        if os.path.isfile(filenameMag):
            imageWidth, imageHeight, self._render_image(filenameMag, x, y, width=self.MAP_SIZE)
            self._figure_label(x, y+imageHeight, "Theoretical Ideal: Catalog Mag.")

        x += self.MAP_SIZE + self.SPACING
        filenameMagBias = filename.replace(server, "catalog-magnitude-bias")
        if os.path.isfile(filenameMagBias):
            imageWidth, imageHeight = self._render_image(filenameMagBias, x, y, width=self.MAP_SIZE)
            self._figure_label(x, y+imageHeight, "Theoretical Ideal: Catalog Mag. w/Bias")
        return

    def _render_event_error(self, event):
        """Figure of magnitude and location error.
        """
        x = self.MARGIN
        y = self.MARGIN

        plots_dir = self.config.get("files", "plots_dir")
        label = analysis_event_label(self.config, event["event_id"])

        filename = os.path.join(plots_dir, label+"-alert_error.png")
        self._render_image(filename, x, y, width=2.0*self.MAP_SIZE)
        return

    def _render_event_mmi_correlation(self, event):
        """Figure of MMI correlation (observed vs predicted) with inset
        of residual histogram.
        """
        x = self.MARGIN
        y = 0.5*self.PAGE_HEIGHT

        plots_dir = self.config.get("files", "plots_dir")
        label = analysis_event_label(self.config, event["event_id"])

        filename = os.path.join(plots_dir, label+"-mmi_correlation.png")
        self._render_image(filename, x, y, height=self.MAP_SIZE)
        return

    def _render_event_mmi_warningtime(self, event):
        """Figure of MMI correlation (observed vs predicted) with inset
        of residual histogram.
        """
        x = 0.5*self.PAGE_WIDTH
        y = 0.5*self.PAGE_HEIGHT

        plots_dir = self.config.get("files", "plots_dir")
        label = analysis_event_label(self.config, event["event_id"])

        filename = os.path.join(plots_dir, label+"-warning_time_mmi.png")
        self._render_image(filename, x, y, height=self.MAP_SIZE)
        return

    def _render_event_info(self, event, shakemap, alerts):
        x = self.MARGIN
        y = self.PAGE_HEIGHT-(self.MARGIN+self.HEADER)

        self.canvas.saveState()
        self.canvas.translate(x, y)
        
        ot = dateutil.parser.parse(event["origin_time"])
        text = self.canvas.beginText()
        text.setFont("Courier", 8)
        text.textLine("ANSS")
        text.textLine("   {event[magnitude_type]}{event[magnitude]:.1f}".format(event=event))
        text.textLine("   {ot:%Y-%m-%d %H:%M:%S.%f}".format(ot=ot))
        text.textLine("   {event[depth_km]:.1f} km depth".format(event=event))
        text.textLine("ShakeMap")
        text.textLine("   MMI bias {:6.2f}".format(shakemap["mmi_bias"]))
        text.textLine("")
        
        # First alert
        vs = self.config.getfloat("shaking_time", "vs_kmps")
        vp = self.config.getfloat("shaking_time", "vp_kmps")
        text.textLine("P wave arrival at epicenter: {:.1f}s after OT".format(event["depth_km"]/vp))
        if len(alerts) > 0:
            alert = alerts[0]
            text.textLine("First alert")
            text.textLine("   M{:.1f}".format(alert["magnitude"]))
            at = dateutil.parser.parse(alert["timestamp"])
            dt = timedelta_to_seconds(numpy.timedelta64(at-ot))
            text.textLine("   {at:%Y-%m-%d %H:%M:%S.%f} ({dt:.1f}s after OT)".format(at=at, dt=dt))
            text.textLine("   Alert at epicenter: {:.1f}s after P wave".format(dt-event["depth_km"]/vp))
            ts = dt - event["depth_km"]/vs
            tsLabel = "after" if ts > 0 else "before"
            text.textLine("                       {:.1f}s {} S wave".format(ts, tsLabel))
            blindDist = ((dt*vs)**2 - event["depth_km"]**2)**0.5 if dt*vs > event["depth_km"] else 0.0
            text.textLine("   Radius of late alert zone: {:.0f} km".format(blindDist))

        # First alert exceeding threshold
        magThreshold = self.config.getfloat("alerts", "magnitude_threshold")
        thresholdAlert = False
        for alert in alerts:
            if alert["magnitude"] > magThreshold:
                if alert != alerts[0]:
                    thresholdAlert = True
                break
        if thresholdAlert:
            text.textLine("First alert exceeding threshold")
            text.textLine("   M{:.1f}".format(alert["magnitude"]))
            at = dateutil.parser.parse(alert["timestamp"])
            dt = timedelta_to_seconds(numpy.timedelta64(at-ot))
            text.textLine("   {at:%Y-%m-%d %H:%M:%S.%f} ({dt:.1f}s after OT)".format(at=at, dt=dt))
            text.textLine("   Time at epicenter: {:.1f}s after P wave".format(dt-event["depth_km"]/vp))
            ts = dt - event["depth_km"]/vs
            tsLabel = "after" if ts > 0 else "before"
            text.textLine("                      {:.1f}s {} S wave".format(ts, tsLabel))
            blindDist = ((dt*vs)**2 - event["depth_km"]**2)**0.5 if dt > 0 else 0.0
            text.textLine("   Radius of late alert zone: {:.0f} km".format(blindDist))

        self.canvas.drawText(text)
        self.canvas.restoreState()
        return

    def _render_event_perf_table(self, perfEEW, perfTheoryMag, perfTheoryMagBias):
        data = [
            ["Thresholds", "", "Alert Region", "", "Cost Savings", "", "", ""],
            ["Mw", "MMI", "Area\n(km^2)", "Population", "ShakeAlert", "", "Catalog Mag.", "", "Catalog Mag. w/Bias", ""],
            [""]*4 + ["Area", "Pop",]*3,
        ]
        numTableHeaderRows = len(data)
        tableCols = (
            ("magnitude_threshold", "{:3.1f}"),
            ("mmi_threshold", "{:3.1f}"),
            ("area_alert", "{:7.1e}"),
            ("population_alert", "{:7.1e}"),
            ("area_costsavings_eew", "{:5.0f}"),
            ("population_costsavings_eew", "{:8.2e}"),
        )
        
        for pEEW in perfEEW:
            row = [s.format(pEEW[v]) for v,s in tableCols]
            mask = numpy.logical_and(perfTheoryMag["magnitude_threshold"] == pEEW["magnitude_threshold"],
                                         perfTheoryMag["mmi_threshold"] == pEEW["mmi_threshold"])
            if numpy.sum(mask) > 0:
                row += [s.format(perfTheoryMag[mask][0][v]) for v,s in tableCols[-2:]]
            else:
                row += [""]*2
            mask = numpy.logical_and(perfTheoryMagBias["magnitude_threshold"] == pEEW["magnitude_threshold"],
                                         perfTheoryMagBias["mmi_threshold"] == pEEW["mmi_threshold"])
            if numpy.sum(mask) > 0:
                row += [s.format(perfTheoryMagBias[mask][0][v]) for v,s in tableCols[-2:]]
            else:
                row += [""]*2
            data.append(row)

        # Perfect EEW in last row
        areaText = "{:5.0f}".format(perfEEW["area_costsavings_perfecteew"][-1])
        popText = "{:8.2e}".format(perfEEW["population_costsavings_perfecteew"][-1])
        row = ["Perfect EEW"] + [""]*3 + [areaText, popText]*3
        data.append(row)
            
        style = [
            ("FONT", (0,0), (-1,-1), "Courier", 7),
            ("LEFTPADDING", (0,0), (-1,-1), 2),
            ("RIGHTPADDING", (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("TOPPADDING", (0,0), (-1,-1), 2),
            ("GRID", (0,0), (-1,-1), 0.5, (0.5, 0.5, 0.5)),
            ("SPAN", (0,0), (1,0)), # Thresholds
            ("SPAN", (2,0), (3,0)), # Alert Region
            ("SPAN", (4,0), (9,0)), # Cost Savings
            ("SPAN", (0,1), (0,2)), # Mw
            ("SPAN", (1,1), (1,2)), # MMI
            ("SPAN", (2,1), (2,2)), # Area
            ("SPAN", (3,1), (3,2)), # Population
            ("SPAN", (4,1), (5,1)),
            ("SPAN", (6,1), (7,1)),
            ("SPAN", (8,1), (9,1)),
            ("SPAN", (0,-1), (3,-1)),
            ("LINEABOVE", (0,-1), (-1,-1), 1.0, (0,0,0)),
            ("BACKGROUND", (4,-1), (-1,-1), (0.7, 1.0, 1.0)),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ]
        # Highlight row matching alert thresholds
        magThreshold = self.config.getfloat("alerts", "magnitude_threshold")
        mmiThreshold = self.config.getfloat("alerts", "mmi_threshold")
        maskMMI = numpy.ma.masked_values(perfEEW["mmi_threshold"], mmiThreshold).mask
        maskMag = numpy.ma.masked_values(perfEEW["magnitude_threshold"], magThreshold).mask
        row = numTableHeaderRows + numpy.argmax(numpy.logical_and(maskMMI, maskMag))
        style.append(("BACKGROUND", (0,row),(-1,row), (1.0, 1.0, 0.0)))
                
        # Highlight all cases with maximum Q-area and Q-pop
        if perfEEW["population_costsavings_eew"].shape[-1] > 0:
            maxQ = numpy.max(perfEEW["population_costsavings_eew"])
            rowsMaxQ = numTableHeaderRows + numpy.where(perfEEW["population_costsavings_eew"] >= maxQ)[0]
            for row in rowsMaxQ:
                style.append(("BACKGROUND", (-6,row),(-6,row), (0.7, 1.0, 0.7)))
                             
        if perfEEW["area_costsavings_eew"].shape[-1] > 0:
            maxQ = numpy.max(perfEEW["area_costsavings_eew"])
            rowMaxQ = numTableHeaderRows + numpy.where(perfEEW["area_costsavings_eew"] >= maxQ)[0]
            for row in rowsMaxQ:
                style.append(("BACKGROUND", (-5,row),(-5,row), (0.7, 1.0, 0.7)))



        t = Table(data, style=style)
        w, h = t.wrap(0.5*self.PAGE_WIDTH, self.PAGE_HEIGHT-2.0*self.MARGIN)

        self.canvas.saveState()
        self.canvas.translate(0.5*self.PAGE_WIDTH, self.PAGE_HEIGHT-(self.MARGIN+self.HEADER)-h)
        t.drawOn(self.canvas, *self._coord(0.0, 0.0, inch)) #0.0, y-2.0, inch))

        return

    def _figure_label(self, x, y, label):
        """
        """
        self.canvas.saveState()
        self.canvas.translate(x, y)
        text = self.canvas.beginText()
        text.setFont("Helvetica-Bold", 10)
        text.textLines(label)
        self.canvas.drawText(text)
        self.canvas.restoreState()
        return

    
    def _render_image(self, filename, x, y, width=None, height=None):
        image = Image.open(filename)
        if width is None and height is None:
            raise ValueError("Missing image 'width' or 'height'.")
            
        w = width if width else height*image.width/image.height
        h = height if height else width*image.height/image.width

        self.canvas.drawImage(ImageReader(image), x, y, width=w, height=h)
        return (w,h)
    
    def _coord(self, x, y, unit=1):
        return x * unit, y * unit

        
# End of file
