"""
Tests for channel security and private channel membership
"""
import pytest
from app.models.channel import Channel
from app.models.tenant import TenantMembership
from app import db


class TestChannelSecurity:
    """Test suite for channel access control and security"""

    def test_public_channel_accessible_to_all_tenant_members(self, client, test_user, test_tenant, db_session):
        """Test that all tenant members can access public channels"""
        # Create a public channel
        channel = Channel(
            name='general',
            slug='general',
            tenant_id=test_tenant.id,
            is_private=False,
            created_by_id=test_user.id
        )
        db_session.add(channel)
        db_session.commit()

        # Login as test_user
        client.login(test_user, test_tenant.id)

        # Access public channel
        response = client.get(f'/chat/channel/{channel.slug}')
        assert response.status_code == 200

    def test_private_channel_accessible_to_members_only(self, client, test_user, test_tenant, db_session):
        """Test that only members can access private channels"""
        # Create a private channel with test_user as member
        channel = Channel(
            name='secret',
            slug='secret',
            tenant_id=test_tenant.id,
            is_private=True,
            created_by_id=test_user.id
        )
        db_session.add(channel)
        db_session.flush()

        # Add test_user as member
        channel.add_member(test_user)
        db_session.commit()

        # Login as test_user
        client.login(test_user, test_tenant.id)

        # Should be able to access
        response = client.get(f'/chat/channel/{channel.slug}')
        assert response.status_code == 200

    def test_private_channel_blocks_non_members(self, client, test_user, test_user_2, test_tenant, db_session):
        """Test that non-members cannot access private channels"""
        # Add test_user_2 to the same tenant
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create a private channel with test_user as creator/member (but NOT test_user_2)
        # Use unique slug to avoid any caching issues
        channel = Channel(
            name='secret-blocks-test',
            slug='secret-blocks-test',
            tenant_id=test_tenant.id,
            is_private=True,
            created_by_id=test_user.id
        )
        db_session.add(channel)
        db_session.flush()

        # Add test_user as member but NOT test_user_2
        channel.add_member(test_user)
        db_session.commit()

        # Login as test_user_2 (who is NOT a member of this channel)
        client.login(test_user_2, test_tenant.id)

        # Try to access private channel
        response = client.get(f'/chat/channel/{channel.slug}')
        assert response.status_code == 403

    def test_non_member_cannot_send_messages_to_private_channel(self, client, test_user, test_user_2, test_tenant, db_session):
        """Test that non-members cannot send messages to private channels"""
        # Add test_user_2 to the same tenant
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create a private channel with only test_user as member
        # Use unique slug to avoid caching issues
        channel = Channel(
            name='secret-send-test',
            slug='secret-send-test',
            tenant_id=test_tenant.id,
            is_private=True,
            created_by_id=test_user.id
        )
        db_session.add(channel)
        db_session.flush()

        channel.add_member(test_user)
        db_session.commit()

        # Login as test_user_2 (non-member)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user_2.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to send message
        response = client.post(
            f'/chat/channel/{channel.slug}/send',
            json={'content': 'Hello from non-member'},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 403
        assert b'access' in response.data.lower()

    def test_only_creator_can_add_members_to_private_channel(self, client, test_user, test_user_2, test_tenant, db_session):
        """Test that only channel creator can add members"""
        # Add test_user_2 to the same tenant
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create a private channel with test_user as creator
        # Use unique slug to avoid caching issues
        channel = Channel(
            name='secret-add-test',
            slug='secret-add-test',
            tenant_id=test_tenant.id,
            is_private=True,
            created_by_id=test_user.id
        )
        db_session.add(channel)
        db_session.flush()

        channel.add_member(test_user)
        channel.add_member(test_user_2)  # Add test_user_2 as member but not creator
        db_session.commit()

        # Create a third user to try to add
        from app.models.user import User
        test_user_3 = User(
            email='test3@example.com',
            first_name='Test',
            last_name='User3',
            email_confirmed=True
        )
        test_user_3.set_password('Test123!@#')
        db_session.add(test_user_3)
        db_session.flush()

        # Add to tenant
        membership_3 = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_3.id,
            role='member'
        )
        db_session.add(membership_3)
        db_session.commit()

        # Login as test_user_2 (member but not creator)
        client.login(test_user_2, test_tenant.id)

        # Try to add test_user_3 to channel
        response = client.post(
            f'/chat/channel/{channel.slug}/members/add',
            json={'user_id': test_user_3.id},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code in [302, 403]

    def test_channel_creator_can_add_members(self, client, test_user, test_user_2, test_tenant, db_session):
        """Test that channel creator can successfully add members"""
        # Add test_user_2 to the same tenant
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create a private channel with test_user as creator
        channel = Channel(
            name='secret',
            slug='secret',
            tenant_id=test_tenant.id,
            is_private=True,
            created_by_id=test_user.id
        )
        db_session.add(channel)
        db_session.flush()

        channel.add_member(test_user)
        db_session.commit()

        # Login as test_user (creator)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Add test_user_2 to channel
        response = client.post(
            f'/chat/channel/{channel.slug}/members/add',
            json={'user_id': test_user_2.id},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 200

        # Verify member was added
        channel_check = Channel.query.get(channel.id)
        assert test_user_2 in channel_check.members

    def test_cannot_add_members_to_public_channel(self, client, test_user, test_user_2, test_tenant, db_session):
        """Test that you cannot explicitly add members to public channels"""
        # Add test_user_2 to the same tenant
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create a public channel
        channel = Channel(
            name='general',
            slug='general',
            tenant_id=test_tenant.id,
            is_private=False,
            created_by_id=test_user.id
        )
        db_session.add(channel)
        db_session.commit()

        # Login as test_user (creator)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Try to add member to public channel
        response = client.post(
            f'/chat/channel/{channel.slug}/members/add',
            json={'user_id': test_user_2.id},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 400
        assert b'public' in response.data.lower()

    def test_non_member_cannot_view_channel_mentions(self, client, test_user, test_user_2, test_tenant, db_session):
        """Test that non-members cannot access mention suggestions for private channels"""
        # Add test_user_2 to the same tenant
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create a private channel with only test_user as member
        # Use unique slug to avoid caching issues
        channel = Channel(
            name='secret-mentions-test',
            slug='secret-mentions-test',
            tenant_id=test_tenant.id,
            is_private=True,
            created_by_id=test_user.id
        )
        db_session.add(channel)
        db_session.flush()

        channel.add_member(test_user)
        db_session.commit()

        # Login as test_user_2 (non-member)
        client.login(test_user_2, test_tenant.id)

        # Try to get mentions
        response = client.get(f'/chat/channel/{channel.slug}/mentions')
        assert response.status_code == 403

    def test_creator_can_remove_members_from_private_channel(self, client, test_user, test_user_2, test_tenant, db_session):
        """Test that channel creator can remove members"""
        # Add test_user_2 to the same tenant
        membership = TenantMembership(
            tenant_id=test_tenant.id,
            user_id=test_user_2.id,
            role='member'
        )
        db_session.add(membership)
        db_session.commit()

        # Create a private channel with both users as members
        channel = Channel(
            name='secret',
            slug='secret',
            tenant_id=test_tenant.id,
            is_private=True,
            created_by_id=test_user.id
        )
        db_session.add(channel)
        db_session.flush()

        channel.add_member(test_user)
        channel.add_member(test_user_2)
        db_session.commit()

        # Login as test_user (creator)
        with client.session_transaction() as sess:
            sess['user_id'] = test_user.id
            sess['current_tenant_id'] = test_tenant.id

        # Remove test_user_2
        response = client.post(
            f'/chat/channel/{channel.slug}/members/remove',
            json={'user_id': test_user_2.id},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 200

        # Verify member was removed
        channel_check = Channel.query.get(channel.id)
        assert test_user_2 not in channel_check.members
