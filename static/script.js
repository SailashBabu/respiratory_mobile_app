// Feature group toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    // Update feature sections based on checkbox selection
    const featureCheckboxes = document.querySelectorAll('.feature-group');
    const featureSections = {
        'Demographics': 'demographics-section',
        'Lifestyle': 'lifestyle-section',
        'Air Pollution': 'air-pollution-section',
        'Environment': 'environment-section',
        'Spirometry': 'spirometry-section'
    };

    function updateFeatureSections() {
        const selectedGroups = [];
        
        featureCheckboxes.forEach(checkbox => {
            const sectionId = featureSections[checkbox.value];
            const section = document.getElementById(sectionId);
            
            if (checkbox.checked) {
                if (section) section.style.display = 'block';
                selectedGroups.push(checkbox.value);
            } else {
                if (section) section.style.display = 'none';
            }
        });
        
        // Update hidden input with selected feature groups
        document.getElementById('selected_feature_groups').value = selectedGroups.join(',');
    }

    featureCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateFeatureSections);
    });

    // Initialize sections
    updateFeatureSections();

    // Auto-calculate FEV1/FVC ratio
    const fev1Input = document.getElementById('fev1');
    const fvcInput = document.getElementById('fvc');
    const ratioDisplay = document.getElementById('fev1_fvc_ratio_display');
    const ratioInput = document.getElementById('fev1_fvc_ratio');

    function calculateRatio() {
        const fev1 = parseFloat(fev1Input.value) || 0;
        const fvc = parseFloat(fvcInput.value) || 0;
        
        if (fvc > 0) {
            const ratio = fev1 / fvc;
            ratioDisplay.textContent = ratio.toFixed(2);
            ratioInput.value = ratio;
            
            // Color code based on severity
            if (ratio >= 0.75) {
                ratioDisplay.style.color = '#28a745';
            } else if (ratio >= 0.70) {
                ratioDisplay.style.color = '#fd7e14';
            } else if (ratio >= 0.60) {
                ratioDisplay.style.color = '#dc3545';
            } else {
                ratioDisplay.style.color = '#721c24';
            }
        } else {
            ratioDisplay.textContent = '0.00';
            ratioInput.value = 0;
            ratioDisplay.style.color = '#6c757d';
        }
    }

    if (fev1Input && fvcInput) {
        fev1Input.addEventListener('input', calculateRatio);
        fvcInput.addEventListener('input', calculateRatio);
        calculateRatio(); // Initial calculation
    }

    // Auto-generate patient name with timestamp
    function generatePatientName() {
        const now = new Date();
        const timestamp = now.toISOString().replace(/[-:]/g, '').split('.')[0];
        return `Patient_${timestamp}`;
    }

    const patientNameInput = document.getElementById('patient_name');
    if (patientNameInput && !patientNameInput.value) {
        patientNameInput.value = generatePatientName();
    }
});

// Form validation
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('predictionForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            const selectedGroups = document.getElementById('selected_feature_groups').value;
            if (!selectedGroups) {
                e.preventDefault();
                alert('Please select at least one feature group.');
                return false;
            }
            return true;
        });
    }
});