import Phaser from 'phaser';
import { apiUrl } from './desktopApi';
import { describeMapLoad } from './mapNodes.mjs';

export default class MapScene extends Phaser.Scene {
  constructor() {
    super({ key: 'MapScene' });
  }

  init() {
    this.currentRealm = this.registry.get('currentRealm') || 'Outer Rim';
    this.onSelectRealm = this.registry.get('onSelectRealm');
    this.onMapNodesLoaded = this.registry.get('onMapNodesLoaded');
    this.onMapNodeSelected = this.registry.get('onMapNodeSelected');
    this.onMapStatusChanged = this.registry.get('onMapStatusChanged');
    this.failedAssets = {};
  }

  preload() {
    const t = Date.now();

    // A user-triggered retry restarts this scene. Remove cached assets first so
    // Phaser does not keep a stale image or reject a duplicate texture key.
    for (const key of ['landscape', 'icon_Town', 'icon_Camp', 'icon_Dungeon', 'icon_Boss']) {
      if (this.textures.exists(key)) this.textures.remove(key);
    }
    this.cache.json.remove('overworld_data');
    
    const url = apiUrl(`/api/vault/Realms/${encodeURIComponent(this.currentRealm)}/Overworld.png?t=${t}`);
    this.load.image('landscape', url);
    
    this.load.json('overworld_data', apiUrl(`/api/vault/Realms/${encodeURIComponent(this.currentRealm)}/Overworld.json?t=${t}`));
    
    this.load.svg('icon_Town', `/assets/icons/Town.svg?t=${t}`, { width: 24, height: 24 });
    this.load.svg('icon_Camp', `/assets/icons/Camp.svg?t=${t}`, { width: 24, height: 24 });
    this.load.svg('icon_Dungeon', `/assets/icons/Dungeon.svg?t=${t}`, { width: 24, height: 24 });
    this.load.svg('icon_Boss', `/assets/icons/Boss.svg?t=${t}`, { width: 24, height: 24 });

    this.loadErrorMsg = null;
    this.load.on('loaderror', (file) => {
      if (file.key === 'landscape' || file.key === 'overworld_data') {
        this.failedAssets[file.key] = {
          status: Number(file.xhrLoader?.status) || 0,
        };
      }
    });
  }

  create() {
    this.cameras.main.setBackgroundColor('#09090b');

    // 1. Render Background Landscape Image (Centered to mathematically crop 1024x1024 into 16:9)
    if (this.textures.exists('landscape')) {
      const bg = this.add.image(512, 288, 'landscape').setOrigin(0.5, 0.5);
      const scale = Math.max(1024 / bg.width, 576 / bg.height);
      bg.setScale(scale);
    }

    // 2. Validate source nodes; never synthesize squad, threat, or map locations.
    const overworldData = this.cache.json.get('overworld_data');
    const result = describeMapLoad({
      mapData: overworldData,
      dataLoadError: this.failedAssets.overworld_data,
      imageLoadError: this.failedAssets.landscape,
    });
    const { nodes } = result;
    this.onMapNodesLoaded?.(nodes);
    this.onMapStatusChanged?.({ kind: result.kind, message: result.message });
    this.showMapDataDiagnostic(result);

    // 3. A spline needs at least two points in Phaser.
    if (nodes.length >= 2) {
      const graphics = this.add.graphics();
      const points = nodes.map((node) => new Phaser.Math.Vector2(node.x, node.y));
      const curve = new Phaser.Curves.Spline(points);

      graphics.lineStyle(6, 0x09090b, 0.7);
      curve.draw(graphics, 64);
      graphics.lineStyle(2, 0xffffff, 0.9);
      curve.draw(graphics, 64);
    }

    // 4. Render interactive 3D Miniature Icons for Nodes
    nodes.forEach((node) => {
      
      const iconKey = `icon_${node.type}`;
      const container = this.add.container(node.x, node.y);
      container.setSize(48, 48);
      container.setInteractive({ useHandCursor: true, pixelPerfect: false });
      container.setData('realmName', node.name);
      container.setData('selected', false);

      // Draw the circular background
      const bg = this.add.graphics();
      // Determine theme color based on type
      let themeColor = 0xffffff;
      if (node.type === 'Boss') themeColor = 0xef4444; // Red
      else if (node.type === 'Camp') themeColor = 0x00d4ff; // Cyan
      else if (node.type === 'Dungeon') themeColor = 0x8b5cf6; // Purple
      else if (node.type === 'Town') themeColor = 0xf59e0b; // Amber
      
      // Draw the circular background (offset to 22,22 so it fits entirely inside the 44x44 generated texture)
      bg.fillStyle(themeColor, 0.9);
      bg.lineStyle(2, 0x09090b, 1);
      bg.fillCircle(22, 22, 20);
      bg.strokeCircle(22, 22, 20);
      
      // Generate a texture from the graphics so we can apply WebGL FX to it
      const textureKey = `gem_base_${node.type}`;
      if (!this.textures.exists(textureKey)) {
        bg.generateTexture(textureKey, 44, 44);
      }
      bg.destroy(); // Remove the graphics object
      
      const gemImg = this.add.image(0, 0, textureKey);
      
      // Apply Native WebGL Pipeline Effects (Phaser 3.60+) safely
      if (gemImg.preFX) {
        // 1. Drop Shadow (distance, x, y, color, alpha, blur, iterations)
        gemImg.preFX.addShadow(0, 0, 0.05, 1, 0x000000, 4, 1);
        
        // 2. 3D Bevel Effect (distance, angle, highlightColor, highlightAlpha, shadowColor, shadowAlpha)
        gemImg.preFX.addBevel(2, 0.5, 0xffffff, 0.8, 0x000000, 0.8);
      }
      
      container.add(gemImg);
      
      // SVG Icon
      if (this.textures.exists(iconKey)) {
        const icon = this.add.image(0, 0, iconKey);
        icon.setTint(0xffffff); // Tint FontAwesome SVGs to white
        if (icon.preFX) {
          icon.preFX.addShadow(0, 0, 0.02, 1, 0x000000, 2, 1);
        }
        container.add(icon);
      }

      // Node Label floating underneath (Hidden by default)
      const label = this.add.text(0, 35, node.name, {
        fontFamily: 'monospace',
        fontSize: '14px',
        color: '#00d4ff', // Default to accent color since it only shows on hover
        backgroundColor: '#000000cc',
        padding: { x: 6, y: 3 }
      }).setOrigin(0.5).setVisible(false);
      container.add(label);

      const selectionRing = this.add.graphics();
      selectionRing.lineStyle(3, 0x00d4ff, 1);
      selectionRing.strokeCircle(22, 22, 24);
      selectionRing.setName('realm-selection-ring');
      selectionRing.setVisible(false);
      container.add(selectionRing);

      // Node Hover Interactions
      container.on('pointerover', () => {
        container.setScale(1.2);
        label.setVisible(true);
      });
      container.on('pointerout', () => {
        if (!container.getData('selected')) {
          container.setScale(1);
          label.setVisible(false);
        }
      });
      container.on('pointerup', () => this.selectNode(node.name, container, label, selectionRing));
    });

    this.renderTelemetry(this.registry.get('getMapTelemetry')?.());

    // Camera bounds removed; canvas handles stretching via ENVELOP mode
    // Map fits statically inside the view container.
  }

  selectNode(realmName, container, label, selectionRing) {
    const wasSelected = container.getData('selected');
    this.children.list
      .filter((child) => child.getData?.('mapRealmNode'))
      .forEach((child) => {
        child.setData('selected', false);
        child.setScale(1);
        child.getByName?.('realm-selection-ring')?.setVisible(false);
      });
    container.setData('mapRealmNode', true);
    container.setData('selected', true);
    container.setScale(1.2);
    label.setVisible(true);
    selectionRing.setVisible(true);
    this.events.emit('map-node-selected', { realmName });
    if (!wasSelected || this.registry.get('selectedRealmNode') !== realmName) {
      this.registry.set('selectedRealmNode', realmName);
      this.onMapNodeSelected?.(realmName);
    }
  }

  showMapDataDiagnostic(result) {
    if (result.kind === 'ready') return;

    this.add.text(24, 72, result.message, {
      fontFamily: 'monospace',
      fontSize: '13px',
      color: '#fca5a5',
      backgroundColor: '#09090bcc',
      padding: { x: 10, y: 8 },
      lineSpacing: 4,
      wordWrap: { width: 520 }
    }).setDepth(100);

    this.events.emit('map-data-diagnostic', result);
  }

  renderTelemetry(telemetry) {
    this.telemetryLayer?.destroy(true);
    this.telemetryLayer = this.add.container(0, 0).setDepth(90);
    for (const marker of telemetry?.markers || []) {
      const color = Phaser.Display.Color.HexStringToColor(marker.color).color;
      const dot = this.add.graphics();
      dot.fillStyle(0x09090b, 1);
      dot.fillCircle(marker.x, marker.y, 10);
      dot.lineStyle(3, color, 1);
      dot.strokeCircle(marker.x, marker.y, 8);
      const label = this.add.text(marker.x, marker.y < 32 ? marker.y + 16 : marker.y - 16, marker.label, {
        fontFamily: 'monospace', fontSize: '12px', color: marker.color,
        backgroundColor: '#09090bdd', padding: { x: 4, y: 2 }
      }).setOrigin(marker.x > 768 ? 1 : marker.x < 256 ? 0 : 0.5, marker.y < 32 ? 0 : 1);
      this.telemetryLayer.add([dot, label]);
    }
  }

  update() {}
}
