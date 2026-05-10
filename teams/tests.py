"""
Day 28 — Tests

Covers: auth, team creation, dependency logic, constraint engine,
risk engine, impact prediction, circular dependency detection.

Run with: python manage.py test
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from teams.models import Department, Team, UserPosition
from teams.services import (
    create_team, update_team, delete_team,
    validate_team_structure, validate_department_strength,
    add_member_to_team,
)
from dependencies.models import TeamDependency
from dependencies.services import create_dependency
from intelligence.services import (
    detect_organisational_risks, predict_impact,
    detect_circular_dependencies, get_dependency_chain,
    ask_engie, deep_search,
)
from users.services import register_user, login_user, generate_password_reset_token

User = get_user_model()


# ──────────────────────────────────────────────
# BASE TEST CASE
# ──────────────────────────────────────────────

class EngieTestCase(TestCase):
    """Base class that sets up common test data."""

    def setUp(self):
        """Create a standard set of users, departments, and teams."""
        # Admin user
        self.admin = User.objects.create_superuser(
            email='admin@engie.test',
            username='admin',
            password='AdminPass123!',
            full_name='Admin User',
        )
        # Regular engineer
        self.engineer = User.objects.create_user(
            email='engineer@engie.test',
            username='eng1',
            password='EngPass123!',
            full_name='Alex Engineer',
        )
        # Department
        self.dept = Department.objects.create(
            department_name='Broadcast Engineering',
            head_user=self.admin,
            status=Department.Status.ACTIVE,
        )
        # Teams
        self.team_a = Team.objects.create(
            department=self.dept,
            manager=self.admin,
            team_name='Platform Core',
            status=Team.Status.ACTIVE,
        )
        self.team_b = Team.objects.create(
            department=self.dept,
            manager=self.admin,
            team_name='Broadcast API',
            status=Team.Status.ACTIVE,
        )
        self.team_c = Team.objects.create(
            department=self.dept,
            manager=self.admin,
            team_name='Stream Ops',
            status=Team.Status.ACTIVE,
        )


# ──────────────────────────────────────────────
# AUTH TESTS
# ──────────────────────────────────────────────

class AuthServiceTests(TestCase):

    def test_register_user_success(self):
        """TC-01: Valid registration creates an active UserAccount."""
        user = register_user(
            username='newuser',
            email='new@test.com',
            password='SecurePass123!',
            full_name='New User',
        )
        self.assertIsNotNone(user.pk)
        self.assertTrue(user.is_active)
        self.assertEqual(user.username, 'newuser')
        self.assertEqual(user.avatar_initials, 'NU')  # Auto-generated

    def test_register_duplicate_email_raises(self):
        """TC-02: Duplicate email registration raises ValidationError."""
        register_user('user1', 'dup@test.com', 'Pass123!word', 'User One')
        with self.assertRaises(ValidationError) as ctx:
            register_user('user2', 'dup@test.com', 'Pass123!word', 'User Two')
        self.assertIn('email', ctx.exception.message_dict)

    def test_register_duplicate_username_raises(self):
        """TC-02b: Duplicate username raises ValidationError."""
        register_user('dupuser', 'a@test.com', 'Pass123!word', 'User A')
        with self.assertRaises(ValidationError) as ctx:
            register_user('dupuser', 'b@test.com', 'Pass123!word', 'User B')
        self.assertIn('username', ctx.exception.message_dict)

    def test_register_short_password_raises(self):
        """TC-03: Short password raises ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            register_user('user3', 'c@test.com', 'short', 'User Three')
        self.assertIn('password', ctx.exception.message_dict)

    def test_password_reset_token_generated(self):
        """TC-07: Password reset token is generated for existing email."""
        user = register_user('resetuser', 'reset@test.com', 'Pass123!word', 'Reset User')
        token = generate_password_reset_token('reset@test.com')
        self.assertIsNotNone(token)
        self.assertGreater(len(token), 20)

    def test_password_reset_unknown_email_returns_none(self):
        """TC-07: Unknown email returns None silently (no enumeration)."""
        result = generate_password_reset_token('nobody@unknown.com')
        self.assertIsNone(result)


# ──────────────────────────────────────────────
# TEAM CREATION TESTS
# ──────────────────────────────────────────────

class TeamServiceTests(EngieTestCase):

    def test_create_team_success(self):
        """TC-19: Admin can create a team with audit log written."""
        from notifications.models import AuditLog
        initial_audit_count = AuditLog.objects.count()

        team = create_team(
            actor=self.admin,
            department_id=self.dept.pk,
            team_name='Security Core',
            description='Handles all security.',
        )

        self.assertIsNotNone(team.pk)
        self.assertEqual(team.team_name, 'Security Core')
        self.assertEqual(team.department, self.dept)

        # Audit log should have been written
        self.assertEqual(AuditLog.objects.count(), initial_audit_count + 1)
        log = AuditLog.objects.latest('timestamp')
        self.assertEqual(log.entity_type, 'Team')
        self.assertEqual(log.action, AuditLog.Action.CREATE)

    def test_create_team_blank_name_raises(self):
        """TC-19: Blank team name raises ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            create_team(actor=self.admin, department_id=self.dept.pk, team_name='  ')
        self.assertIn('team_name', ctx.exception.message_dict)

    def test_create_team_invalid_dept_raises(self):
        """TC-19: Non-existent department raises ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            create_team(actor=self.admin, department_id=9999, team_name='Ghost Team')
        self.assertIn('department', ctx.exception.message_dict)

    def test_update_team_records_old_new_values(self):
        """TC-19: Update captures old and new values in audit log."""
        from notifications.models import AuditLog

        update_team(
            actor=self.admin,
            team_id=self.team_a.pk,
            team_name='Platform Core v2',
        )

        log = AuditLog.objects.filter(entity_type='Team', action=AuditLog.Action.UPDATE).latest('timestamp')
        self.assertEqual(log.old_values['team_name'], 'Platform Core')
        self.assertEqual(log.new_values['team_name'], 'Platform Core v2')

    def test_delete_team_disbands_not_hard_delete(self):
        """TC-20: delete_team sets status to DISBANDED, not hard-deletes."""
        team_id = self.team_c.pk
        delete_team(actor=self.admin, team_id=team_id)
        team = Team.objects.get(pk=team_id)
        self.assertEqual(team.status, Team.Status.DISBANDED)

    def test_delete_team_with_active_deps_raises(self):
        """TC-20: Cannot delete a team that other teams depend on."""
        TeamDependency.objects.create(
            upstream_team=self.team_a,
            downstream_team=self.team_b,
            criticality='high',
        )
        with self.assertRaises(ValidationError) as ctx:
            delete_team(actor=self.admin, team_id=self.team_a.pk)
        self.assertIn('dependencies', ctx.exception.message_dict)

    def test_add_member_to_team(self):
        """TC-24: Adding a member creates a UserPosition and activity log."""
        from teams.models import TeamActivity
        from datetime import date

        position = add_member_to_team(
            actor=self.admin,
            team_id=self.team_a.pk,
            user_id=self.engineer.pk,
            job_title='Senior Engineer',
            start_date=date.today(),
        )

        self.assertIsNotNone(position.pk)
        self.assertEqual(position.job_title, 'Senior Engineer')

        # Activity should be recorded
        activity = TeamActivity.objects.filter(
            team=self.team_a,
            action_type=TeamActivity.ActionType.MEMBER_JOINED,
        ).first()
        self.assertIsNotNone(activity)


# ──────────────────────────────────────────────
# CONSTRAINT ENGINE TESTS
# ──────────────────────────────────────────────

class ConstraintEngineTests(EngieTestCase):

    def test_understaffed_team_violation_detected(self):
        """Constraint engine detects teams with < 5 engineers."""
        violations = validate_team_structure(team_id=self.team_a.pk)
        understaffed = [v for v in violations if v.constraint_id == 'MIN_ENGINEERS']
        self.assertTrue(len(understaffed) > 0)
        self.assertIn('Platform Core', understaffed[0].entity)

    def test_unmanaged_team_violation_detected(self):
        """Constraint engine detects teams without a manager."""
        unmanaged = Team.objects.create(
            department=self.dept,
            manager=None,
            team_name='Ghost Team',
            status=Team.Status.ACTIVE,
        )
        violations = validate_team_structure(team_id=unmanaged.pk)
        no_manager = [v for v in violations if v.constraint_id == 'NO_MANAGER']
        self.assertTrue(len(no_manager) > 0)

    def test_department_with_few_teams_flagged(self):
        """Departments with < 3 teams are flagged."""
        # Our test dept has 3 teams but one is DISBANDED
        delete_team(actor=self.admin, team_id=self.team_c.pk)
        violations = validate_department_strength(department_id=self.dept.pk)
        weak = [v for v in violations if v.constraint_id == 'MIN_TEAMS_PER_DEPT']
        self.assertTrue(len(weak) > 0)


# ──────────────────────────────────────────────
# DEPENDENCY LOGIC TESTS
# ──────────────────────────────────────────────

class DependencyServiceTests(EngieTestCase):

    def test_create_dependency_success(self):
        """Dependency creation succeeds with valid teams."""
        dep = create_dependency(
            actor=self.admin,
            upstream_team_id=self.team_a.pk,
            downstream_team_id=self.team_b.pk,
            criticality='high',
        )
        self.assertIsNotNone(dep.pk)
        self.assertEqual(dep.upstream_team, self.team_a)
        self.assertEqual(dep.downstream_team, self.team_b)

    def test_self_dependency_raises(self):
        """A team cannot depend on itself."""
        with self.assertRaises(ValidationError) as ctx:
            create_dependency(
                actor=self.admin,
                upstream_team_id=self.team_a.pk,
                downstream_team_id=self.team_a.pk,
            )
        self.assertIn('dependency', ctx.exception.message_dict)

    def test_duplicate_dependency_raises(self):
        """Duplicate dependency edges are rejected."""
        create_dependency(
            actor=self.admin,
            upstream_team_id=self.team_a.pk,
            downstream_team_id=self.team_b.pk,
        )
        with self.assertRaises(ValidationError):
            create_dependency(
                actor=self.admin,
                upstream_team_id=self.team_a.pk,
                downstream_team_id=self.team_b.pk,
            )

    def test_circular_dependency_blocked(self):
        """Circular dependencies A→B→A are detected and rejected."""
        # A→B is fine
        create_dependency(
            actor=self.admin,
            upstream_team_id=self.team_a.pk,
            downstream_team_id=self.team_b.pk,
        )
        # B→A should be caught as circular
        with self.assertRaises(ValidationError) as ctx:
            create_dependency(
                actor=self.admin,
                upstream_team_id=self.team_b.pk,
                downstream_team_id=self.team_a.pk,
            )
        self.assertIn('circular', ctx.exception.message_dict)


# ──────────────────────────────────────────────
# INTELLIGENCE ENGINE TESTS
# ──────────────────────────────────────────────

class RiskEngineTests(EngieTestCase):

    def test_risk_engine_detects_unmanaged_team(self):
        """Risk engine flags teams without a manager."""
        unmanaged = Team.objects.create(
            department=self.dept,
            manager=None,
            team_name='Unmanaged Team',
            status=Team.Status.ACTIVE,
        )
        risks = detect_organisational_risks()
        no_manager_risks = [r for r in risks if r.risk_type == 'NO_MANAGER']
        team_names = [r.team_name for r in no_manager_risks]
        self.assertIn('Unmanaged Team', team_names)

    def test_risk_engine_detects_bottleneck(self):
        """Risk engine detects high-fan-out teams (bottlenecks)."""
        # Create 5+ teams that all depend on team_a
        for i in range(5):
            extra_team = Team.objects.create(
                department=self.dept,
                team_name=f'Consumer Team {i}',
                status=Team.Status.ACTIVE,
            )
            TeamDependency.objects.create(
                upstream_team=self.team_a,
                downstream_team=extra_team,
            )

        risks = detect_organisational_risks()
        spof_risks = [r for r in risks if r.risk_type in ('SINGLE_POINT_OF_FAILURE', 'BOTTLENECK')]
        team_names = [r.team_name for r in spof_risks]
        self.assertIn('Platform Core', team_names)

    def test_impact_prediction_low_for_isolated_team(self):
        """Impact prediction returns LOW for a team with no downstream deps."""
        result = predict_impact(self.team_c.pk)
        self.assertEqual(result['impact_level'], 'LOW')
        self.assertEqual(result['affected_count'], 0)

    def test_impact_prediction_reflects_downstream_count(self):
        """Impact prediction returns correct affected team count."""
        # B depends on A, C depends on A → 2 affected if A fails
        TeamDependency.objects.create(upstream_team=self.team_a, downstream_team=self.team_b)
        TeamDependency.objects.create(upstream_team=self.team_a, downstream_team=self.team_c)

        result = predict_impact(self.team_a.pk)
        self.assertEqual(result['affected_count'], 2)
        self.assertIn('Broadcast API', result['affected_teams'])
        self.assertIn('Stream Ops', result['affected_teams'])

    def test_circular_detection_finds_cycle(self):
        """DFS cycle detection finds A→B→A cycles."""
        # Manually insert circular deps (bypassing service to test detection)
        TeamDependency.objects.create(upstream_team=self.team_a, downstream_team=self.team_b)
        TeamDependency.objects.create(upstream_team=self.team_b, downstream_team=self.team_a)

        cycles = detect_circular_dependencies()
        self.assertTrue(len(cycles) > 0)

    def test_dependency_chain_bfs_traversal(self):
        """BFS chain traversal returns correct depth and teams."""
        TeamDependency.objects.create(upstream_team=self.team_a, downstream_team=self.team_b)
        TeamDependency.objects.create(upstream_team=self.team_b, downstream_team=self.team_c)

        result = get_dependency_chain(self.team_a.pk, direction='downstream')
        self.assertIn('Broadcast API', result['chain'])
        self.assertIn('Stream Ops', result['chain'])
        self.assertEqual(result['total_affected'], 2)

    def test_deep_search_finds_team(self):
        """Deep search returns a team by partial name match."""
        result = deep_search('Platform')
        team_results = [r for r in result['results'] if r['type'] == 'team']
        names = [r['name'] for r in team_results]
        self.assertIn('Platform Core', names)

    def test_deep_search_short_query_rejected(self):
        """Deep search rejects queries under 2 characters."""
        result = deep_search('a')
        self.assertIn('message', result)
        self.assertEqual(result['total'], 0)

    def test_ask_engie_owner_intent(self):
        """Ask Engie resolves 'who manages' to the team manager."""
        result = ask_engie('Who manages Platform Core?')
        self.assertEqual(result.get('intent'), 'owner')
        self.assertEqual(result['answer']['manager'], 'Admin User')

    def test_ask_engie_empty_query(self):
        """Ask Engie returns an error for empty input."""
        result = ask_engie('')
        self.assertIn('error', result)


# ──────────────────────────────────────────────
# PERMISSION TESTS
# ──────────────────────────────────────────────

class PermissionTests(EngieTestCase):

    def test_non_admin_cannot_delete_team_via_service(self):
        """
        TC-21: Engineers cannot call delete_team.
        Note: the API view enforces this; the service itself doesn't re-check role
        (that's the view's job). This test documents the boundary clearly.
        The API should return 403 for engineers.
        """
        # This test documents expected behavior via the API layer
        # Service itself is admin-gated via the view
        # Here we test the view layer using the test client
        from django.test import Client
        client = Client()
        client.login(username='engineer@engie.test', password='EngPass123!')

        response = client.delete(f'/api/teams/{self.team_a.pk}/')
        # Should be 403 Forbidden for non-admin
        self.assertEqual(response.status_code, 403)
