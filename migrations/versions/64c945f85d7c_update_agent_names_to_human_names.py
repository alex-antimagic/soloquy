"""update_agent_names_to_human_names

Revision ID: 64c945f85d7c
Revises: 3a01de80b661
Create Date: 2025-11-06 12:45:51.731080

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '64c945f85d7c'
down_revision = '3a01de80b661'
branch_labels = None
depends_on = None


def upgrade():
    # Update agent names from "X Assistant" to human first names
    # Executive -> Evan
    op.execute("""
        UPDATE agents
        SET name = 'Evan'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Executive'
        AND agents.name = 'Executive Assistant'
    """)

    # Finance -> Fiona
    op.execute("""
        UPDATE agents
        SET name = 'Fiona'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Finance'
        AND agents.name = 'Finance Assistant'
    """)

    # Marketing -> Maya
    op.execute("""
        UPDATE agents
        SET name = 'Maya'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Marketing'
        AND agents.name = 'Marketing Assistant'
    """)

    # Sales -> Sam
    op.execute("""
        UPDATE agents
        SET name = 'Sam'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Sales'
        AND agents.name = 'Sales Assistant'
    """)

    # Support -> Sarah
    op.execute("""
        UPDATE agents
        SET name = 'Sarah'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Support'
        AND agents.name = 'Support Assistant'
    """)

    # Product -> Parker
    op.execute("""
        UPDATE agents
        SET name = 'Parker'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Product'
        AND agents.name = 'Product Assistant'
    """)

    # Legal -> Larry
    op.execute("""
        UPDATE agents
        SET name = 'Larry'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Legal'
        AND agents.name = 'Legal Assistant'
    """)

    # HR/People -> Hannah
    op.execute("""
        UPDATE agents
        SET name = 'Hannah'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'HR/People'
        AND agents.name = 'HR/People Assistant'
    """)

    # IT/Engineering -> Ian
    op.execute("""
        UPDATE agents
        SET name = 'Ian'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'IT/Engineering'
        AND agents.name = 'IT/Engineering Assistant'
    """)


def downgrade():
    # Revert agent names back to "X Assistant" format
    # Evan -> Executive Assistant
    op.execute("""
        UPDATE agents
        SET name = 'Executive Assistant'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Executive'
        AND agents.name = 'Evan'
    """)

    # Fiona -> Finance Assistant
    op.execute("""
        UPDATE agents
        SET name = 'Finance Assistant'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Finance'
        AND agents.name = 'Fiona'
    """)

    # Maya -> Marketing Assistant
    op.execute("""
        UPDATE agents
        SET name = 'Marketing Assistant'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Marketing'
        AND agents.name = 'Maya'
    """)

    # Sam -> Sales Assistant
    op.execute("""
        UPDATE agents
        SET name = 'Sales Assistant'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Sales'
        AND agents.name = 'Sam'
    """)

    # Sarah -> Support Assistant
    op.execute("""
        UPDATE agents
        SET name = 'Support Assistant'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Support'
        AND agents.name = 'Sarah'
    """)

    # Parker -> Product Assistant
    op.execute("""
        UPDATE agents
        SET name = 'Product Assistant'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Product'
        AND agents.name = 'Parker'
    """)

    # Larry -> Legal Assistant
    op.execute("""
        UPDATE agents
        SET name = 'Legal Assistant'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'Legal'
        AND agents.name = 'Larry'
    """)

    # Hannah -> HR/People Assistant
    op.execute("""
        UPDATE agents
        SET name = 'HR/People Assistant'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'HR/People'
        AND agents.name = 'Hannah'
    """)

    # Ian -> IT/Engineering Assistant
    op.execute("""
        UPDATE agents
        SET name = 'IT/Engineering Assistant'
        FROM departments
        WHERE agents.department_id = departments.id
        AND departments.name = 'IT/Engineering'
        AND agents.name = 'Ian'
    """)
