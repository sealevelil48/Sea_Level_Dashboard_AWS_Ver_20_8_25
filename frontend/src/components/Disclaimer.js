import React from 'react';
import './Disclaimer.css';

const Disclaimer = () => {
  return (
    <div className="disclaimer-container">
      <div className="disclaimer-header">
        <h1>Disclaimer & Terms of Use</h1>
        <p>Sea Level Dashboard - Important Legal Information</p>
      </div>

      <div className="disclaimer-content">
        <div className="disclaimer-warning-box">
          <strong>⚠️ IMPORTANT:</strong> Please read this disclaimer carefully before using the Sea Level Dashboard application. Your use of this application constitutes acceptance of these terms.
        </div>
        
        <div className="disclaimer-section">
          <h2>1. General Information & Purpose</h2>
          <p>The Sea Level Dashboard application (the &quot;App&quot;) provides sea level measurements, wave forecasts, and related oceanographic data for informational and educational purposes only. The information presented should not be considered as professional advice or a substitute for official reports, government advisories, or expert consultation.</p>
          <p>This App is intended for general awareness and research purposes. Users requiring precise, real-time data for critical decision-making should consult official maritime authorities and professional services.</p>
        </div>
        
        <div className="disclaimer-section">
          <h2>2. Data Accuracy & Limitations</h2>
          <p>While we strive to provide reliable and accurate information, we cannot guarantee:</p>
          <ul>
            <li>The accuracy, completeness, or timeliness of any data presented</li>
            <li>Uninterrupted access to sensor data or third-party services</li>
            <li>Real-time synchronization with actual sea conditions</li>
            <li>The reliability of predictive models or forecasts</li>
          </ul>
          <p>Data may be affected by sensor malfunctions, network issues, processing delays, or environmental factors beyond our control. Historical data may be revised without notice.</p>
        </div>
        
        <div className="disclaimer-section">
          <h2>3. Prohibited Uses & Safety Warning</h2>
          <div className="disclaimer-warning-box">
            <strong>This App SHALL NOT be used for:</strong>
            <ul>
              <li>Maritime navigation or route planning</li>
              <li>Safety-critical operations or emergency response</li>
              <li>Commercial fishing or shipping operations</li>
              <li>Any activity where inaccurate data could lead to personal injury, property damage, or environmental harm</li>
              <li>Legal, insurance, or regulatory compliance purposes</li>
            </ul>
          </div>
          <p>Always consult official government sources, maritime authorities, and qualified professionals for critical decision-making. In case of emergency, contact local emergency services immediately.</p>
        </div>
        
        <div className="disclaimer-section">
          <h2>4. Data Sources & Attribution</h2>
          <div className="disclaimer-data-source-box">
            <h3>Primary Data Sources:</h3>
            <ul>
              <li><strong>Sea Level Measurements:</strong> Proprietary sensor network deployed across coastal monitoring stations</li>
              <li><strong>Wave Forecast Data:</strong> Israel Meteorological Service (IMS) - Used under applicable terms</li>
              <li><strong>Mapping Services:</strong> GovMap API and OpenStreetMap contributors</li>
              <li><strong>Predictive Models:</strong> Internal algorithms (ARIMA, Kalman Filter, Ensemble methods)</li>
            </ul>
            <p style={{ marginTop: '15px', fontSize: '0.95rem', color: '#718096' }}>We acknowledge and respect the intellectual property rights of all third-party data providers. The use of third-party data is subject to their respective terms and conditions.</p>
          </div>
        </div>
        
        <div className="disclaimer-section">
          <h2>5. Limitation of Liability</h2>
          <p>TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW:</p>
          <ul>
            <li>The App is provided &quot;AS IS&quot; and &quot;AS AVAILABLE&quot; without warranties of any kind</li>
            <li>We disclaim all warranties, express or implied, including but not limited to merchantability, fitness for a particular purpose, and non-infringement</li>
            <li>In no event shall the developers, operators, or data providers be liable for any direct, indirect, incidental, special, consequential, or punitive damages</li>
            <li>This includes, without limitation, damages for loss of profits, data, use, goodwill, or other intangible losses</li>
          </ul>
        </div>
        
        <div className="disclaimer-section">
          <h2>6. Intellectual Property Rights</h2>
          <p>All content, features, and functionality of this App, including but not limited to text, graphics, logos, and software, are the exclusive property of the App operators or licensed to us, and are protected by intellectual property laws.</p>
          <p>Users may not reproduce, distribute, modify, or create derivative works without explicit written permission, except for personal, non-commercial use.</p>
        </div>
        
        <div className="disclaimer-section">
          <h2>7. Privacy & Data Collection</h2>
          <p>The App may collect anonymous usage statistics to improve service quality. We do not collect personal information unless explicitly provided by users. Any data collection is subject to applicable privacy laws and regulations.</p>
          <p>By using this App, you consent to the collection and use of anonymous usage data as described above.</p>
        </div>
        
        <div className="disclaimer-section">
          <h2>8. Third-Party Services</h2>
          <p>This App integrates with various third-party services and APIs. We are not responsible for:</p>
          <ul>
            <li>The availability, accuracy, or reliability of third-party services</li>
            <li>Changes to third-party APIs that may affect App functionality</li>
            <li>Content or practices of third-party websites linked from this App</li>
          </ul>
        </div>
        
        <div className="disclaimer-section">
          <h2>9. Indemnification</h2>
          <p>You agree to indemnify, defend, and hold harmless the App operators, developers, and data providers from any claims, losses, damages, liabilities, and expenses (including legal fees) arising from your use of the App or violation of these terms.</p>
        </div>
        
        <div className="disclaimer-section">
          <h2>10. Modifications to Terms</h2>
          <p>We reserve the right to modify these terms at any time without prior notice. Continued use of the App following any modifications constitutes acceptance of the updated terms. Users should review these terms periodically.</p>
        </div>
        
        <div className="disclaimer-section">
          <h2>11. Governing Law & Jurisdiction</h2>
          <p>These terms shall be governed by and construed in accordance with the laws of the State of Israel, without regard to its conflict of law provisions. Any disputes shall be subject to the exclusive jurisdiction of the courts in Jerusalem, Israel.</p>
        </div>
        
        <div className="disclaimer-section">
          <h2>12. Contact Information</h2>
          <p>For questions, concerns, or feedback regarding this disclaimer or the App, please contact us through the appropriate channels provided in the application.</p>
        </div>
        
        <div className="disclaimer-highlight-box">
          <strong>By using this App, you acknowledge that you have read, understood, and agree to be bound by all terms outlined in this disclaimer.</strong>
        </div>
        
        <p className="last-updated">Last Updated: September 2025 | Version 1.0</p>
      </div>
      
      <div className="disclaimer-footer">
        <p>© 2025 Survey of Israel. All rights reserved.</p>
      </div>
    </div>
  );
};

export default Disclaimer;