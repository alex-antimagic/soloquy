# Agent Avatar Setup Guide

## ✅ Current Status

All agents now have placeholder avatars using UI Avatars service!

### Configured Agents

| Agent | Department | Avatar Color |
|-------|-----------|--------------|
| Evan | Executive | Dark Gray (#4A5568) |
| Fiona | Finance | Very Dark (#2D3748) |
| Maya | Marketing | Pink (#ED64A6) |
| Sam | Sales | Green (#48BB78) |
| Sarah | Support | Blue (#4299E1) |
| Parker | Product | Purple (#9F7AEA) |
| Larry | Legal | Black (#1A202C) |
| Hannah | HR/People | Light Pink (#F687B3) |
| Ian | IT/Engineering | Dark Blue (#2C5282) |

## 🎨 Upgrading to Real Headshots

### Step 1: Download Headshots

Visit [https://instaheadshots.com/](https://instaheadshots.com/) and download professional headshots:

**Suggested Matches:**
- **Evan** (male, professional/executive look)
- **Fiona** (female, analytical/finance professional)
- **Maya** (female, creative/marketing professional)
- **Sam** (gender-neutral, friendly/sales professional)
- **Sarah** (female, helpful/support professional)
- **Parker** (gender-neutral, strategic/product manager)
- **Larry** (male, serious/legal professional)
- **Hannah** (female, warm/HR professional)
- **Ian** (male, technical/engineering professional)

### Step 2: Save Images

Save the downloaded headshots in:
```
app/static/images/avatars/
```

With these filenames:
- `evan.jpg`
- `fiona.jpg`
- `maya.jpg`
- `sam.jpg`
- `sarah.jpg`
- `parker.jpg`
- `larry.jpg`
- `hannah.jpg`
- `ian.jpg`

### Step 3: Update Database

Run the update script:
```bash
source venv/bin/activate
python update_agent_avatars.py --local
```

This will update all agent avatars to use the local image files.

## 📝 Management Commands

### View Current Avatar Status
```bash
python update_agent_avatars.py --status
```

### Reset to Placeholders
```bash
python update_agent_avatars.py --placeholders
```

### Use Local Images
```bash
python update_agent_avatars.py --local
```

## 🎨 UI Updates

The following templates now display agent avatars:

1. **Conversations Sidebar** (`app/templates/components/conversations_sidebar.html`)
   - Shows 24x24px rounded avatar next to agent names
   - Fallback to status indicator if no avatar

2. **CSS Styling** (`app/static/css/style.css`)
   - `.conversation-avatar` class for consistent styling
   - Border highlighting on hover and active states
   - Responsive circular avatars

## 🔄 Future Enhancements

Consider adding avatars to:
- [ ] Chat message headers (show agent avatar next to each message)
- [ ] Agent detail pages
- [ ] Department overview pages
- [ ] Search results
- [ ] @mention suggestions

## 💡 Tips

1. **Image Size**: Recommended 200x200px or larger for crisp display
2. **Format**: JPG or PNG work well
3. **Background**: Clean, professional backgrounds work best
4. **Lighting**: Well-lit headshots look more professional
5. **Expression**: Friendly but professional expressions
6. **Consistency**: Try to match the lighting/style across all avatars

## 🆘 Troubleshooting

**Avatars not showing?**
1. Check file paths: `app/static/images/avatars/[name].jpg`
2. Verify file permissions: `chmod 644 app/static/images/avatars/*`
3. Clear browser cache: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
4. Check database: `python update_agent_avatars.py --status`

**Wrong avatar showing?**
1. Verify agent name matches filename
2. Check database: `python update_agent_avatars.py --status`
3. Re-run update: `python update_agent_avatars.py --local`

---

**Last Updated**: November 7, 2025
