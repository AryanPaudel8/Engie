"""
Engie — Seed Data Script
Run: python seed_data.py
Creates demo data matching the coursework brief (Broadcast Company scenario)
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from datetime import date, timedelta
from users.models import UserAccount
from teams.models import Department, Team, UserPosition, Repository, Contact, TeamActivity
from dependencies.models import TeamDependency
from notifications.models import Notification, AuditLog
from messaging.models import Message, MessageRecipient
from scheduling.models import ScheduleEvent, EventParticipant

print("🌱 Seeding Engie demo data...")

# ── USERS ──────────────────────────────────────────────
admin = UserAccount.objects.create_superuser(
    email='admin@broadcast.com',
    username='admin',
    password='Admin1234!',
    full_name='Admin User',
)
admin.role = 'admin'
admin.save()

s_patel = UserAccount.objects.create_user(
    email='s.patel@broadcast.com', username='spatel',
    password='Engineer1!', full_name='S. Patel',
)
s_patel.role = 'manager'; s_patel.save()

j_rahman = UserAccount.objects.create_user(
    email='j.rahman@broadcast.com', username='jrahman',
    password='Engineer1!', full_name='J. Rahman',
)
j_rahman.role = 'manager'; j_rahman.save()

a_torres = UserAccount.objects.create_user(
    email='a.torres@broadcast.com', username='atorres',
    password='Engineer1!', full_name='A. Torres',
)
a_torres.role = 'manager'; a_torres.save()

l_chen = UserAccount.objects.create_user(
    email='l.chen@broadcast.com', username='lchen',
    password='Engineer1!', full_name='L. Chen',
)
l_chen.role = 'manager'; l_chen.save()

p_williams = UserAccount.objects.create_user(
    email='p.williams@broadcast.com', username='pwilliams',
    password='Engineer1!', full_name='P. Williams',
)
p_williams.role = 'manager'; p_williams.save()

engineers = []
eng_data = [
    ('aryan.paudel@broadcast.com', 'aryanp', 'Aryan Paudel'),
    ('alice.k@broadcast.com', 'alicek', 'Alice Kim'),
    ('bob.m@broadcast.com', 'bobm', 'Bob Martinez'),
    ('carol.h@broadcast.com', 'carolh', 'Carol Hassan'),
    ('david.r@broadcast.com', 'davidr', 'David Ruiz'),
    ('emma.w@broadcast.com', 'emmaw', 'Emma Wilson'),
    ('frank.o@broadcast.com', 'franko', 'Frank Osei'),
    ('grace.l@broadcast.com', 'gracel', 'Grace Li'),
]
for email, uname, fname in eng_data:
    u = UserAccount.objects.create_user(email=email, username=uname, password='Engineer1!', full_name=fname)
    engineers.append(u)

print(f"  ✓ Created {UserAccount.objects.count()} users")

# ── DEPARTMENTS ─────────────────────────────────────────
dept_broadcast = Department.objects.create(
    head_user=s_patel,
    department_name='Broadcast Engineering',
    description='Core broadcast systems and stream delivery',
    status='active',
    email_distribution='broadcast-eng@broadcast.com',
)
dept_platform = Department.objects.create(
    head_user=j_rahman,
    department_name='Platform',
    description='Infrastructure & tooling for all engineering teams',
    status='active',
    email_distribution='platform@broadcast.com',
)
dept_data = Department.objects.create(
    head_user=l_chen,
    department_name='Data & Analytics',
    description='Data pipelines and business insights',
    status='restructuring',
    email_distribution='data@broadcast.com',
)
dept_devops = Department.objects.create(
    head_user=a_torres,
    department_name='DevOps',
    description='Deployment & operations',
    status='active',
    email_distribution='devops@broadcast.com',
)
dept_security = Department.objects.create(
    head_user=p_williams,
    department_name='Security',
    description='Cybersecurity & compliance',
    status='active',
    email_distribution='security@broadcast.com',
)
dept_ops = Department.objects.create(
    department_name='Operations',
    description='Legacy & general ops',
    status='disbanded',
    email_distribution='ops@broadcast.com',
)

print(f"  ✓ Created {Department.objects.count()} departments")

# ── TEAMS ──────────────────────────────────────────────
team_broadcast_api = Team.objects.create(
    department=dept_broadcast, manager=s_patel,
    team_name='Broadcast API',
    description='Public broadcast API serving all external clients',
    mission_purpose='Deliver reliable, low-latency broadcast API',
    status='active',
)
team_stream_ops = Team.objects.create(
    department=dept_broadcast, manager=a_torres,
    team_name='Stream Ops',
    description='Live stream operations and monitoring',
    mission_purpose='24/7 stream reliability and incident response',
    status='active',
)
team_platform_core = Team.objects.create(
    department=dept_platform, manager=j_rahman,
    team_name='Platform Core',
    description='Core infrastructure & Platform engineering',
    mission_purpose='Build reliable platform for all engineering teams',
    status='active',
)
team_devops = Team.objects.create(
    department=dept_devops, manager=a_torres,
    team_name='DevOps',
    description='CI/CD pipelines and deployment automation',
    mission_purpose='Accelerate delivery through automation',
    status='active',
)
team_data_pipeline = Team.objects.create(
    department=dept_data, manager=l_chen,
    team_name='Data Pipeline',
    description='Real-time and batch data processing pipelines',
    mission_purpose='Deliver high-quality data to all consumers',
    status='restructuring',
)
team_security_core = Team.objects.create(
    department=dept_security, manager=p_williams,
    team_name='Security Core',
    description='Threat detection, compliance, and security tooling',
    mission_purpose='Protect all company assets and ensure compliance',
    status='active',
)
team_legacy = Team.objects.create(
    department=dept_ops, manager=None,
    team_name='Legacy Ops',
    description='Maintenance of legacy broadcast infrastructure',
    mission_purpose='Keep legacy systems operational until migration complete',
    status='disbanded',
)

print(f"  ✓ Created {Team.objects.count()} teams")

# ── USER POSITIONS ──────────────────────────────────────
positions = [
    (s_patel, team_broadcast_api, 'Engineering Manager'),
    (engineers[0], team_broadcast_api, 'Senior Software Engineer'),
    (engineers[1], team_broadcast_api, 'Software Engineer'),
    (engineers[2], team_broadcast_api, 'Software Engineer'),
    (engineers[3], team_broadcast_api, 'QA Engineer'),
    (j_rahman, team_platform_core, 'Engineering Manager'),
    (engineers[4], team_platform_core, 'Senior Platform Engineer'),
    (engineers[5], team_platform_core, 'Infrastructure Engineer'),
    (a_torres, team_stream_ops, 'Engineering Manager'),
    (engineers[6], team_stream_ops, 'Stream Engineer'),
    (engineers[7], team_stream_ops, 'Operations Engineer'),
    (l_chen, team_data_pipeline, 'Engineering Manager'),
    (p_williams, team_security_core, 'Security Lead'),
    (a_torres, team_devops, 'DevOps Lead'),
]
for user, team, title in positions:
    UserPosition.objects.get_or_create(
        user=user, team=team,
        defaults={'job_title': title, 'start_date': date(2024, 1, 15)}
    )

print(f"  ✓ Created {UserPosition.objects.count()} positions")

# ── REPOSITORIES ───────────────────────────────────────
repos = [
    (team_broadcast_api, 'broadcast-api', 'git', 'https://github.com/broadcast/broadcast-api', True),
    (team_broadcast_api, 'broadcast-api-docs', 'git', 'https://github.com/broadcast/broadcast-api-docs', False),
    (team_platform_core, 'platform-core', 'git', 'https://github.com/broadcast/platform-core', True),
    (team_stream_ops, 'stream-ops', 'git', 'https://github.com/broadcast/stream-ops', True),
    (team_data_pipeline, 'data-pipeline', 'git', 'https://github.com/broadcast/data-pipeline', True),
    (team_security_core, 'security-tooling', 'git', 'https://github.com/broadcast/security-tooling', True),
    (team_devops, 'devops-config', 'git', 'https://github.com/broadcast/devops-config', True),
]
for team, name, rtype, url, is_main in repos:
    Repository.objects.create(team=team, repo_name=name, repo_type=rtype, url=url, is_main=is_main,
                               last_commit_date=timezone.now() - timedelta(hours=2))

print(f"  ✓ Created {Repository.objects.count()} repositories")

# ── CONTACTS ───────────────────────────────────────────
contacts = [
    (team_broadcast_api, 'slack', '#broadcast-api', True),
    (team_broadcast_api, 'email', 'broadcast-api@broadcast.com', True),
    (team_platform_core, 'slack', '#platform-core', True),
    (team_platform_core, 'jira', 'https://jira.broadcast.com/platform', True),
    (team_stream_ops, 'slack', '#stream-ops', True),
    (team_data_pipeline, 'slack', '#data-pipeline', True),
    (team_security_core, 'slack', '#security-core', True),
    (team_devops, 'slack', '#devops', True),
]
for team, ctype, value, is_primary in contacts:
    Contact.objects.create(team=team, contact_type=ctype, contact_value=value, is_primary=is_primary)

print(f"  ✓ Created {Contact.objects.count()} contacts")

# ── DEPENDENCIES ───────────────────────────────────────
deps = [
    (team_platform_core, team_broadcast_api, 'service', 'Platform provides infra for Broadcast API', 'high'),
    (team_platform_core, team_stream_ops, 'service', 'Platform provides infra for Stream Ops', 'critical'),
    (team_platform_core, team_data_pipeline, 'service', 'Platform provides infra for Data Pipeline', 'medium'),
    (team_broadcast_api, team_stream_ops, 'api', 'Stream Ops calls Broadcast API for stream metadata', 'high'),
    (team_security_core, team_broadcast_api, 'compliance', 'Broadcast API must pass security review', 'medium'),
    (team_devops, team_platform_core, 'tooling', 'DevOps manages platform deployments', 'high'),
]
for upstream, downstream, dtype, desc, criticality in deps:
    TeamDependency.objects.get_or_create(
        upstream_team=upstream, downstream_team=downstream,
        defaults={'dependency_type': dtype, 'description': desc, 'criticality': criticality}
    )

print(f"  ✓ Created {TeamDependency.objects.count()} dependencies")

# ── ACTIVITIES ──────────────────────────────────────────
activities = [
    (team_stream_ops, a_torres, 'team_created', 'Stream Ops team created by A. Torres'),
    (team_data_pipeline, l_chen, 'status_changed', 'Data Pipeline marked as restructuring'),
    (team_platform_core, j_rahman, 'member_joined', '3 engineers joined Platform Core'),
    (team_legacy, admin, 'status_changed', 'Legacy Ops disbanded'),
    (team_broadcast_api, s_patel, 'repo_added', 'Broadcast API repo updated'),
]
for team, user, action, desc in activities:
    TeamActivity.objects.create(team=team, user=user, action_type=action, description=desc)

print(f"  ✓ Created {TeamActivity.objects.count()} activities")

# ── NOTIFICATIONS ───────────────────────────────────────
Notification.objects.create(
    user=engineers[0], type='info', title='New team dependency added',
    content='Platform Core → Broadcast API dependency created',
)
Notification.objects.create(
    user=engineers[0], type='warning', title='Team understaffed',
    content='Stream Ops has fewer than recommended engineers',
)
Notification.objects.create(
    user=s_patel, type='info', title='New member joined',
    content='Alice Kim joined Broadcast API team',
)

print(f"  ✓ Created {Notification.objects.count()} notifications")

# ── MESSAGES ────────────────────────────────────────────
msg1 = Message.objects.create(
    sender=s_patel,
    subject='Downstream dependency sync',
    message_content='Hey team, can we sync on the downstream dependency between Broadcast API and Stream Ops? We\'re seeing some latency issues.',
    status='sent',
)
MessageRecipient.objects.create(message=msg1, user=engineers[0])
MessageRecipient.objects.create(message=msg1, user=a_torres)

msg2 = Message.objects.create(
    sender=l_chen,
    subject='Restructuring update: team merger',
    message_content='Data Pipeline team restructuring is underway. Please check the dependency diagram in Engie first.',
    status='sent',
)
MessageRecipient.objects.create(message=msg2, user=engineers[0])

print(f"  ✓ Created {Message.objects.count()} messages")

# ── SCHEDULE EVENTS ─────────────────────────────────────
event1 = ScheduleEvent.objects.create(
    team=team_broadcast_api,
    created_by=s_patel,
    title='Dep Sync - Broadcast API & Stream Ops',
    description='Weekly sync on downstream dependencies and latency',
    event_type='meeting',
    start_datetime=timezone.now() + timedelta(days=2, hours=10),
    end_datetime=timezone.now() + timedelta(days=2, hours=11),
    platform='Google Meet',
    meeting_link='https://meet.google.com/abc-defg-hij',
    color='#7c3aed',
)
EventParticipant.objects.create(event=event1, user=s_patel, role='host', attendance_status='accepted')
EventParticipant.objects.create(event=event1, user=a_torres, role='attendee', attendance_status='pending')
EventParticipant.objects.create(event=event1, user=engineers[0], role='attendee', attendance_status='pending')

event2 = ScheduleEvent.objects.create(
    team=team_platform_core,
    created_by=j_rahman,
    title='Platform Review',
    event_type='review',
    start_datetime=timezone.now() + timedelta(days=4, hours=14),
    end_datetime=timezone.now() + timedelta(days=4, hours=15),
    platform='Zoom',
    color='#3fb950',
)
EventParticipant.objects.create(event=event2, user=j_rahman, role='host', attendance_status='accepted')

print(f"  ✓ Created {ScheduleEvent.objects.count()} events")

print("""
✅ Seed data complete!

Login credentials:
  Admin:    admin@broadcast.com  /  Admin1234!
  Manager:  s.patel@broadcast.com /  Engineer1!
  Engineer: aryan.paudel@broadcast.com / Engineer1!

Run: python manage.py runserver
Then open: http://localhost:8000
""")
