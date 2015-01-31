'''
Module containing methods for processing signals generated by model objects lifecycle.
'''

from django.dispatch import receiver
from django.db.models.signals import post_save
from django.conf import settings
from cog.plugins.esgf.security import esgfDatabaseManager
from django.contrib.auth.signals import user_logged_in

from cog.models import UserProfile, Project
from cog.utils import getJson
from cog.models.peer_site import getPeerSites
from cog.views.utils import get_all_projects_for_user

# callback receiver function for UserProfile post_save events
@receiver(post_save, sender=UserProfile, dispatch_uid="user_profile_post_save")
def account_created_receiver(sender, **kwargs):

    # retrieve arguments
    userp = kwargs['instance']
    created = kwargs['created']

    print 'Signal received: UserProfile post_save: username=%s created=%s openids=%s' % (userp.user.username, created, userp.openids())

    # create ESGF user: only when user profile is first created
    # from a COG registration, and only if the user does NOT have an openid already
    # (as a result of logging in with an ESGF openid)
    if settings.ESGF_CONFIG and created and len(userp.openids())==0:
        print 'Inserting user into ESGF security database'
        esgfDatabaseManager.insertUser(userp)

def update_user_projects_at_login(sender, user, request, **kwargs):
    '''Updates the user projects every time the user logs in.'''
    
    update_user_projects(user)
        
def update_user_projects(user):
    '''
    Function to update the user projects across the federation.
    Will query all remote sites 
    (but NOT the current site, since that information should already be up-to-date) 
    and save the updated information in the local database.
    '''

    if user.is_authenticated():
        
        # retrieve map of (project, groups) for this user
        projTuples = get_all_projects_for_user(user, includeCurrentSite=False)
        
        # update information in local database
        for (project, roles) in projTuples:
            print 'Updating membership for user: %s project: %s' % (user.profile.openid(), project.short_name)   
                    
            # remove all current memberships for this user, project
            for group in project.getGroups():
                user.groups.remove( group )
                
            # insert new memberships for this user, project
            for role in roles:
                group = project.getGroup(role)
                if not group in user.groups.all():
                    user.groups.add(group) 
                                   
        # persist changes to local database
        user.save()
    
# NOTE: connecting the login signal is not needed because every time the user logs in,
# the session is refreshed and updating of projects is triggered already by the CoG session middleware
#user_logged_in.connect(update_user_projects_at_login)