import datetime
import httplib
import logging
import re
import urllib2
import utils
import urlparse
from collections import defaultdict
import pdb

from legistar.scraper import LegistarScraper
from legistar.config import Config, DEFAULT_CONFIG

log = logging.getLogger(__name__)


class HostedLegistarSiteWrapper (object):
    """
    A facade over the Philadelphia city council legistar site data.  It is
    responsible for scraping data out of the site.  The main external point
    of interaction is scrape_legis_file.

    requires: BeautifulSoup, mechanize
    """

    def __init__(self, **options):
        self.scraper = LegistarScraper(options)
        self.legislation_summaries =  self.scraper.searchLegislation('')

    def scrape_legis_file(self, key, summary):
        '''Extract a record from the given document (soup). The key is for the
           sake of record-keeping.  It is the key passed to the site URL.'''

        try:
            legislation_attrs, legislation_history = self.scraper.expandLegislationSummary(summary)
        except urllib2.URLError:
            print 'skipping to next leg record'
            summary = self.legislation_summaries.next()
            legislation_attrs, legislation_history = self.scraper.expandLegislationSummary(summary)


        parsed_url = urlparse.urlparse(summary['URL'])
        key = urlparse.parse_qs(parsed_url.query)['ID'][0]
        
        # re-order the sponsor name by '[First] [Last]' instead of '[Last], [First]'
        sponsors = legislation_attrs['Sponsors']
        first_name_first_sponsors = []
        for sponsor in sponsors :
            if ',' in sponsor :
                name_list = sponsor.split(',')
                name_list.reverse()
                sponsor = ' '.join(name_list)
            first_name_first_sponsors.append(sponsor)

        record = {
            'key' : key,
            'id' : summary['Record #'],
            'url' : summary['URL'],
            'type' : summary['Type'],
            'status' : summary['Status'],
            'title' : summary['Title'],
            'controlling_body' : legislation_attrs['Current Controlling Legislative Body'],
            'intro_date' : self.convert_date(summary['Intro Date']),
            'final_date' : self.convert_date(summary.setdefault('Final Date', '')),
            'version' : summary.setdefault('Version', ''),
            #'contact' : None,
            'sponsors' : first_name_first_sponsors,
            # probably remove this from the model as well
            'minutes_url'  : None
        }

        try:
            attachments = legislation_attrs['Attachments']
            for attachment in attachments:
                attachment['key'] = key
                attachment['file'] = attachment['label']
                del attachment['label']
        except KeyError:
            attachments = []

        actions = []
        for act in legislation_history :
            act_details, act_votes = self.scraper.expandHistorySummary(act)
            action = {
                'key' : key,
                'date_taken' : self.convert_date(act['Date']),
                'acting_body' : act['Action By']['label'],
                'motion' : act['Result'],
                'description' : act['Status']
            }
            actions.append(action)

        # we should probably remove this from the model since the hosted
        # legistar does not have minutes
        minutes = []

        log.info('Scraped legfile with key %r' % (key,))
        log.debug("%r %r %r %r" % (record, attachments, actions, minutes))

        return record, attachments, actions, minutes

    def convert_date(self, orig_date):
        if orig_date:
            return datetime.datetime.strptime(orig_date, '%m/%d/%Y').date()
        else:
            return ''


    def check_for_new_content(self, last_key):
        '''Grab the next legislation summary row. Doesn't use the last_key
           parameter; just starts at the beginning for each instance of the
           scraper.
        '''
        try:
            print 'next leg record'
            next_summary = self.legislation_summaries.next()
            return 0, next_summary
        except StopIteration:
            return None, None

    def init_pdf_cache(self, pdf_mapping) :
        pass
        
    
