/**
 * Bug Report Handler
 * Handles screenshot upload, AI analysis, and ticket submission
 */

(function() {
    'use strict';

    // DOM elements
    const screenshotInput = document.getElementById('bugScreenshot');
    const screenshotPreview = document.getElementById('screenshotPreview');
    const previewImage = document.getElementById('previewImage');
    const aiAnalysisLoading = document.getElementById('aiAnalysisLoading');
    const subjectInput = document.getElementById('bugSubject');
    const descriptionInput = document.getElementById('bugDescription');
    const priorityInput = document.getElementById('bugPriority');
    const screenshotUrlInput = document.getElementById('screenshotUrl');
    const submitButton = document.getElementById('submitBugReport');
    const bugReportForm = document.getElementById('bugReportForm');
    const bugReportModal = document.getElementById('bugReportModal');

    // State
    let currentScreenshotUrl = '';
    let isAnalyzing = false;

    // Reset form when modal is closed
    if (bugReportModal) {
        bugReportModal.addEventListener('hidden.bs.modal', function () {
            resetForm();
        });
    }

    function resetForm() {
        bugReportForm.reset();
        screenshotPreview.style.display = 'none';
        aiAnalysisLoading.style.display = 'none';
        currentScreenshotUrl = '';
        screenshotUrlInput.value = '';
        previewImage.src = '';
        isAnalyzing = false;
        submitButton.disabled = false;
    }

    // Handle screenshot upload
    if (screenshotInput) {
        screenshotInput.addEventListener('change', handleScreenshotUpload);
    }

    async function handleScreenshotUpload(event) {
        const file = event.target.files[0];

        if (!file) {
            screenshotPreview.style.display = 'none';
            return;
        }

        // Validate file type
        const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif'];
        if (!validTypes.includes(file.type)) {
            alert('Please upload a valid image file (PNG, JPG, GIF)');
            screenshotInput.value = '';
            return;
        }

        // Validate file size (10MB max)
        const maxSize = 10 * 1024 * 1024;
        if (file.size > maxSize) {
            alert('File size must be less than 10MB');
            screenshotInput.value = '';
            return;
        }

        // Show preview
        const reader = new FileReader();
        reader.onload = function(e) {
            previewImage.src = e.target.result;
            screenshotPreview.style.display = 'block';
        };
        reader.readAsDataURL(file);

        // Automatically analyze screenshot
        await analyzeScreenshot(file);
    }

    async function analyzeScreenshot(file) {
        if (isAnalyzing) return;

        isAnalyzing = true;
        aiAnalysisLoading.style.display = 'block';
        submitButton.disabled = true;

        // Disable form fields during analysis
        subjectInput.disabled = true;
        descriptionInput.disabled = true;
        priorityInput.disabled = true;

        try {
            const formData = new FormData();
            formData.append('screenshot', file);
            formData.append('current_url', window.location.href);

            const response = await fetch('/support/bug-report/analyze', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken()
                },
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to analyze screenshot');
            }

            const result = await response.json();

            // Pre-fill form with AI suggestions
            subjectInput.value = result.subject;
            descriptionInput.value = result.description;
            priorityInput.value = result.priority;

            // Store screenshot URL
            currentScreenshotUrl = result.screenshot_url;
            screenshotUrlInput.value = result.screenshot_url;

        } catch (error) {
            console.error('Error analyzing screenshot:', error);
            alert('Failed to analyze screenshot: ' + error.message + '\nYou can still submit the bug report manually.');
        } finally {
            aiAnalysisLoading.style.display = 'none';
            isAnalyzing = false;
            submitButton.disabled = false;

            // Re-enable form fields
            subjectInput.disabled = false;
            descriptionInput.disabled = false;
            priorityInput.disabled = false;
        }
    }

    // Handle form submission
    if (submitButton) {
        submitButton.addEventListener('click', handleSubmit);
    }

    async function handleSubmit(event) {
        event.preventDefault();

        // Validate form
        if (!bugReportForm.checkValidity()) {
            bugReportForm.reportValidity();
            return;
        }

        // Get form values
        const subject = subjectInput.value.trim();
        const description = descriptionInput.value.trim();
        const priority = priorityInput.value;
        const screenshotUrl = screenshotUrlInput.value;

        if (!subject || !description) {
            alert('Please provide a subject and description');
            return;
        }

        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...';

        try {
            // Get Support department (for auto-assignment)
            const departmentResponse = await fetch('/api/departments?name=Support', {
                headers: {
                    'X-CSRFToken': getCSRFToken()
                }
            });

            let departmentId = null;
            if (departmentResponse.ok) {
                const departments = await departmentResponse.json();
                if (departments && departments.length > 0) {
                    departmentId = departments[0].id;
                }
            }

            // Create ticket
            const ticketData = {
                subject: subject,
                description: description,
                priority: priority,
                category: 'Bug Report',
                source: 'web',
                screenshot_url: screenshotUrl || null,
                department_id: departmentId
            };

            const response = await fetch('/support/tickets/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify(ticketData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to create ticket');
            }

            const result = await response.json();

            // Success!
            alert(`Bug report submitted successfully! Ticket number: ${result.ticket_number}`);

            // Close modal
            const modal = bootstrap.Modal.getInstance(bugReportModal);
            if (modal) {
                modal.hide();
            }

            // Optionally redirect to ticket
            // window.location.href = `/support/tickets/${result.id}`;

        } catch (error) {
            console.error('Error submitting bug report:', error);
            alert('Failed to submit bug report: ' + error.message);
        } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="bi bi-send"></i> Submit Bug Report';
        }
    }

    // Helper function to get CSRF token
    function getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

})();
