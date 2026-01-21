# KPI-Based Bonus System - Access Guide

## ✅ Fixed: Bonus Dashboard is Now Accessible!

The bonus management system is now fully accessible with multiple entry points from your HR dashboard.

---

## 🚪 How to Access the Bonus Dashboard

### Option 1: Header Button (Fastest)
1. Go to **HR Dashboard** (`/hr`)
2. Look for the **"Bonuses"** button in the top-right header
3. Click it to go directly to `/hr/bonuses`

### Option 2: Featured Metric Card
1. Go to **HR Dashboard** (`/hr`)
2. Below the main metrics, you'll see a highlighted **"KPI-Based Bonuses"** card
3. Click the card to access the bonus dashboard
4. **Note**: Only visible to workspace admins/owners

### Option 3: Quick Actions Sidebar
1. Go to **HR Dashboard** (`/hr`)
2. On the right sidebar, look for **"Quick Actions"** card
3. Click **"KPI-Based Bonuses"** (trophy icon)
4. **Note**: Only visible to workspace admins/owners

### Option 4: HR Navigation Menu
1. Go to **HR Dashboard** (`/hr`)
2. In the right sidebar, find the **"HR Navigation"** card
3. Click **"KPI-Based Bonuses"** at the bottom of the list
4. **Note**: Only visible to workspace admins/owners

### Option 5: Direct URL
Simply navigate to: **`https://worklead.ai/hr/bonuses`**

---

## 🔐 Permission Requirements

**Who Can Access:**
- Workspace Owners
- Workspace Admins

**Who Cannot Access:**
- Regular members (non-admin)

If you're a workspace admin and still can't see it, make sure:
1. You're logged in
2. You've selected the correct workspace
3. The HR applet is enabled for your workspace

---

## 📊 What You'll Find in the Bonus Dashboard

### Main Sections:

1. **YTD Summary Cards**
   - Total revenue for the year
   - Net revenue
   - Average monthly revenue
   - Months where bonuses were calculated

2. **Recent Months Performance**
   - Monthly revenue tracking
   - Data source indicator (QuickBooks vs Manual)
   - Bonus calculation status
   - Quick actions to calculate bonuses

3. **Active Bonus Rules**
   - Currently configured KPI rules
   - Revenue thresholds
   - Bonus types

4. **Recent Calculations**
   - Audit log of bonus calculations
   - Number of bonuses created
   - Total amounts
   - Calculation status

---

## 🎯 Quick Start Guide

### First-Time Setup:

1. **Access the Dashboard**
   - Go to `/hr/bonuses` using any method above

2. **Create a Bonus Rule**
   - Click "Bonus Rules" button
   - Click "New Rule"
   - Configure:
     - Rule name: "Monthly Revenue Goal"
     - Metric: Net Revenue
     - Operator: >=
     - Threshold: $300,000
     - Bonus type: Performance
   - Save

3. **Enter Financial Data**
   - Click "Financial Metrics"
   - Click edit for current month
   - Enter revenue and expenses
   - Or click "Sync from QuickBooks"
   - Save

4. **Calculate Bonuses**
   - Go back to dashboard
   - Find the month in "Recent Months Performance"
   - Click the calculator icon
   - Review created bonuses at `/hr/compensation`
   - Approve individual bonuses

---

## 🔄 Monthly Workflow

**At the Start of Each Month:**

1. Enter or sync previous month's financial data
2. Review active bonus rules
3. Trigger bonus calculation
4. Review pending bonuses in Compensation
5. Approve/adjust bonuses as needed

**Optional: Set Up Automation**
- Configure monthly cron job to auto-calculate
- Receive email notifications when bonuses are ready
- Review and approve via email links

---

## 🎨 Visual Updates

The HR dashboard now includes:

✅ **New "Bonuses" button** in header (admins only)
✅ **Highlighted metric card** for KPI-Based Bonuses
✅ **Quick Actions link** with trophy icon
✅ **HR Navigation link** in sidebar menu

All links point to the same destination: `/hr/bonuses`

---

## 📱 Mobile Access

The bonus dashboard is fully responsive and works on:
- Desktop computers
- Tablets
- Mobile phones

Simply navigate to the same URLs on any device.

---

## 🐛 Troubleshooting

### Issue: Can't see bonus links
**Solution**: Make sure you're an admin/owner in the workspace

### Issue: "Bonuses" button not showing
**Solution**:
1. Hard refresh the page (Cmd+Shift+R or Ctrl+Shift+R)
2. Clear browser cache
3. Verify you're logged in as admin

### Issue: 404 error on `/hr/bonuses`
**Solution**:
1. Restart the Flask application
2. Verify the deployment completed successfully
3. Check that bonus routes are registered

### Issue: Blank page
**Solution**:
1. Check browser console for JavaScript errors
2. Verify templates exist in `/app/templates/hr/bonuses/`
3. Check that database migrations were applied

---

## 📞 Need Help?

If you're still having issues accessing the bonus system:

1. Check **DEPLOYMENT_COMPLETE.md** for full deployment details
2. Verify migrations were applied: `python3 -m flask db current`
3. Check server logs for errors
4. Ensure you're accessing as a workspace admin/owner

---

## ✨ Next Steps

Once you can access the dashboard:

1. ✅ Create your first bonus rule
2. ✅ Enter financial metrics for a month
3. ✅ Run a test calculation
4. ✅ Review and approve bonuses
5. ⏳ Set up QuickBooks integration (optional)
6. ⏳ Schedule monthly cron job (optional)

---

**Last Updated**: January 21, 2026
**Status**: ✅ Fully Accessible with Multiple Entry Points
